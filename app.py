import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timezone, timedelta

# --- PAGE CONFIG ---
st.set_page_config(page_title="Moneymaker Pro", layout="wide")

# --- INITIALIZE SESSION STATE ---
if "promo_queue" not in st.session_state:
    st.session_state.promo_queue = []
if "results" not in st.session_state:
    st.session_state.results = []

# --- HELPERS ---
def convert_american_to_decimal(american_odds):
    return (american_odds / 100) + 1 if american_odds > 0 else (100 / abs(american_odds)) + 1

BOOK_MAP = {
    "All": "all", "theScore Bet": "espnbet", "FanDuel": "fanduel", "DraftKings": "draftkings",
    "Bet365": "bet365", "BetMGM": "betmgm", "Caesars": "williamhill_us", "Fanatics": "fanatics"
}
VALID_BOOKS = [v for k, v in BOOK_MAP.items() if v != "all"]

SPORT_MAP = {
    "NBA": ["basketball_nba"], 
    "NHL": ["icehockey_nhl"], 
    "MLB": ["baseball_mlb"],
    "NCAAB": ["basketball_ncaab"], 
    "Tennis": ["tennis_atp_miami_open"], 
    "All H2H Sports": ["basketball_nba", "icehockey_nhl", "baseball_mlb"]
}

# --- CUSTOM CSS ---
st.markdown("""
    <style>
    [data-testid="stSidebar"] { display: none; }
    .stTable { font-size: 0.85rem; }
    .promo-header { 
        background-color: #1E1E1E; 
        color: white; 
        padding: 8px 15px; 
        border-radius: 5px; 
        margin-top: 25px;
        margin-bottom: 10px; 
        font-weight: bold;
    }
    div[data-testid="stExpander"] { border: none !important; box-shadow: none !important; }
    </style>
    """, unsafe_allow_html=True)

st.title("💰 Multi-Promo Optimizer")

# --- 1. PROMO INPUT ---
with st.container(border=True):
    st.markdown("**Add Promo to Queue**")
    c1, c2, c3, c4 = st.columns(4)
    with c1: p_type = st.selectbox("Strategy", ["Profit Boost (%)", "Bonus Bet", "No-Sweat Bet", "Standard Arb"])
    with c2: p_wager = st.number_input("Wager ($)", value=50.0, step=5.0)
    with c3: p_source = st.selectbox("Source Book", list(BOOK_MAP.keys()), index=1)
    with c4: p_hedge = st.selectbox("Hedge Book", list(BOOK_MAP.keys()), index=0)

    c2_1, c2_2, c2_3 = st.columns([1, 1, 1])
    with c2_1: p_boost = st.number_input("Boost %", value=50) if p_type == "Profit Boost (%)" else 0
    with c2_2: p_sport = st.selectbox("Sport Category", list(SPORT_MAP.keys()))
    with c2_3:
        st.write("")
        if st.button("➕ Add to Queue", use_container_width=True, type="primary"):
            st.session_state.promo_queue.append({
                "Strategy": p_type, "Wager": p_wager, "Source": p_source, 
                "Hedge": p_hedge, "Boost": f"{p_boost}%" if p_type == "Profit Boost (%)" else "-", 
                "Sport": p_sport, "raw_boost": p_boost
            })
            st.rerun()

# --- 2. CONDENSED QUEUE VIEW ---
if st.session_state.promo_queue:
    st.subheader("📋 Pending Queue")
    df_queue = pd.DataFrame(st.session_state.promo_queue).drop(columns=['raw_boost'])
    st.table(df_queue) 
    
    qc1, qc2 = st.columns([1, 4])
    if qc1.button("🗑️ Clear Queue", use_container_width=True):
        st.session_state.promo_queue = []
        st.session_state.results = []
        st.rerun()

    # --- SCAN LOGIC ---
    if st.button("🚀 RUN OPTIMIZED SCAN ALL", type="primary", use_container_width=True):
        api_key = st.secrets.get("ODDS_API_KEY")
        if not api_key:
            st.error("Missing API Key in Secrets (ODDS_API_KEY).")
        else:
            # Step 1: Deduplicate sports to call API only once per sport
            required_sport_codes = set()
            for p in st.session_state.promo_queue:
                required_sport_codes.update(SPORT_MAP[p['Sport']])
            
            cached_data = {}
            for sport_code in required_sport_codes:
                with st.spinner(f"Fetching {sport_code}..."):
                    url = f"https://api.the-odds-api.com/v4/sports/{sport_code}/odds/"
                    params = {'apiKey': api_key, 'regions': 'us', 'markets': 'h2h', 'oddsFormat': 'american'}
                    try:
                        res = requests.get(url, params=params)
                        if res.status_code == 200:
                            cached_data[sport_code] = res.json()
                    except: continue

            # Step 2: Process results
            all_found = []
            now = datetime.now(timezone.utc)
            
            for promo in st.session_state.promo_queue:
                target_codes = SPORT_MAP[promo['Sport']]
                promo_matches = []
                
                for code in target_codes:
                    if code not in cached_data: continue
                    for game in cached_data[code]:
                        g_time = datetime.fromisoformat(game['commence_time'].replace('Z', '+00:00'))
                        if g_time < now + timedelta(minutes=2): continue
                        
                        source_prices, hedge_prices = [], []
                        s_key, h_key = BOOK_MAP[promo['Source']], BOOK_MAP[promo['Hedge']]
                        
                        for bm in game['bookmakers']:
                            if s_key == "all" or bm['key'] == s_key:
                                for out in bm['markets'][0]['outcomes']:
                                    source_prices.append({'team': out['name'], 'price': out['price'], 'book': bm['title'], 'key': bm['key']})
                            if h_key == "all" or bm['key'] == h_key:
                                for out in bm['markets'][0]['outcomes']:
                                    hedge_prices.append({'team': out['name'], 'price': out['price'], 'book': bm['title'], 'key': bm['key']})

                        for s in source_prices:
                            best_h = max([h for h in hedge_prices if h['team'] != s['team'] and h['key'] != s['key']], key=lambda x: x['price'], default=None)
                            if best_h:
                                s_dec, h_dec = convert_american_to_decimal(s['price']), convert_american_to_decimal(best_h['price'])
                                
                                if promo['Strategy'] == "Profit Boost (%)":
                                    boosted_s = 1 + ((s_dec - 1) * (1 + (promo['raw_boost'] / 100)))
                                    h_wag = (promo['Wager'] * boosted_s) / h_dec
                                    profit = (promo['Wager'] * boosted_s) - (promo['Wager'] + h_wag)
                                elif promo['Strategy'] == "Bonus Bet":
                                    h_wag = (promo['Wager'] * (s_dec - 1)) / h_dec
                                    profit = (promo['Wager'] * (s_dec - 1)) - h_wag
                                else:
                                    h_wag = (promo['Wager'] * s_dec) / h_dec
                                    profit = (promo['Wager'] * s_dec) - (promo['Wager'] + h_wag)

                                roi = (profit / promo['Wager']) * 100
                                if roi >= -15:
                                    promo_matches.append({
                                        "promo_id": f"{promo['Source']} {promo['Strategy']} ({promo['Boost']})",
                                        "game": f"{game['away_team']} vs {game['home_team']}",
                                        "profit": profit, "roi": roi, "h_wager": h_wag,
                                        "s_team": s['team'], "s_price": s['price'], "s_book": s['book'],
                                        "h_team": best_h['team'], "h_price": best_h['price'], "h_book": best_h['book']
                                    })
                # Take Top 3 for this specific promo
                all_found.extend(sorted(promo_matches, key=lambda x: x['roi'], reverse=True)[:3])
            
            st.session_state.results = all_found

# --- 3. DISPLAY CATEGORIZED RESULTS ---
if st.session_state.results:
    st.markdown("---")
    grouped = {}
    for res in st.session_state.results:
        if res['promo_id'] not in grouped: grouped[res['promo_id']] = []
        grouped[res['promo_id']].append(res)

    for promo_name, matches in grouped.items():
        st.markdown(f'<div class="promo-header">🏆 Top Results: {promo_name}</div>', unsafe_allow_html=True)
        
        # Dynamic columns to prevent IndexError
        num_matches = len(matches)
        cols = st.columns(num_matches if num_matches > 0 else 1)
        
        for i, match in enumerate(matches):
            with cols[i]:
                with st.container(border=True):
                    st.markdown(f"**{match['game']}**")
                    st.success(f"Profit: **${match['profit']:.2f}** ({match['roi']:.1f}%)")
                    st.caption(f"Bet {match['s_team']} @ {match['s_price']} ({match['s_book']})")
                    st.caption(f"Hedge {match['h_team']} @ {match['h_price']} ({match['h_book']})")
                    st.warning(f"Hedge Wager: **${match['h_wager']:.2f}**")

elif st.session_state.promo_queue and "results" in st.session_state:
    st.info("No profitable matches found yet. Try running the scan or adjusting your books.")

# --- FOOTER ---
st.markdown("<br><br>", unsafe_allow_html=True)
if st.session_state.results:
    if st.button("Reset Everything"):
        st.session_state.promo_queue = []
        st.session_state.results = []
        st.rerun()
