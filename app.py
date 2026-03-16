import streamlit as st
import requests
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

# --- STRICT BOOKMAKER MAPPING ---
BOOK_MAP = {
    "theScore Bet": "espnbet", 
    "FanDuel": "fanduel", 
    "DraftKings": "draftkings",
    "Bet365": "bet365", 
    "BetMGM": "betmgm", 
    "Caesars": "williamhill_us", 
    "Fanatics": "fanatics"
}
VALID_API_KEYS = list(BOOK_MAP.values())

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
    /* Tighten up the row spacing */
    [data-testid="stVerticalBlock"] > div { padding-top: 0rem; padding-bottom: 0rem; }
    .promo-header { 
        background-color: #1E1E1E; color: white; padding: 10px 15px; 
        border-radius: 8px; margin-top: 20px; margin-bottom: 10px; font-weight: bold;
    }
    .queue-text { font-size: 0.85rem; margin: 0; padding: 0; line-height: 1.2; }
    .detail-label { color: #666; font-size: 0.7rem; text-transform: uppercase; font-weight: bold; }
    .detail-value { font-size: 0.85rem; font-weight: 500; margin-bottom: 5px; }
    </style>
    """, unsafe_allow_html=True)

st.title("💰 Multi-Promo Optimizer")

# --- 1. PROMO INPUT ---
with st.container(border=True):
    c1, c2, c3, c4 = st.columns(4)
    with c1: p_type = st.selectbox("Strategy", ["Profit Boost (%)", "Bonus Bet", "No-Sweat Bet", "Standard Arb"])
    with c2: p_wager = st.number_input("Wager ($)", value=50.0, step=5.0)
    with c3: p_source = st.selectbox("Source Book", ["All"] + list(BOOK_MAP.keys()), index=1)
    with c4: p_hedge = st.selectbox("Hedge Book", ["All"] + list(BOOK_MAP.keys()), index=0)

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

# --- 2. TIGHTENED INTERACTIVE QUEUE ---
if st.session_state.promo_queue:
    st.subheader("📋 Pending Queue")
    
    # Header Row (More condensed ratios)
    h_col = st.columns([2.5, 0.8, 1.2, 1.2, 1.2, 0.4])
    h_col[0].caption("PROMO / BOOST")
    h_col[1].caption("WAGER")
    h_col[2].caption("SOURCE")
    h_col[3].caption("HEDGE")
    h_col[4].caption("SPORT")
    
    # Row Loop
    for idx, promo in enumerate(st.session_state.promo_queue):
        r_col = st.columns([2.5, 0.8, 1.2, 1.2, 1.2, 0.4])
        
        r_col[0].markdown(f'<p class="queue-text"><b>{promo["Strategy"]}</b> ({promo["Boost"]})</p>', unsafe_allow_html=True)
        r_col[1].markdown(f'<p class="queue-text">${promo["Wager"]:.0f}</p>', unsafe_allow_html=True)
        r_col[2].markdown(f'<p class="queue-text">{promo["Source"]}</p>', unsafe_allow_html=True)
        r_col[3].markdown(f'<p class="queue-text">{promo["Hedge"]}</p>', unsafe_allow_html=True)
        r_col[4].markdown(f'<p class="queue-text">{promo["Sport"]}</p>', unsafe_allow_html=True)
        
        if r_col[5].button("🗑️", key=f"del_{idx}"):
            st.session_state.promo_queue.pop(idx)
            st.rerun()

    st.write("") # Tiny spacer before scan button
    if st.button("🚀 RUN OPTIMIZED SCAN ALL", type="primary", use_container_width=True):
        api_key = st.secrets.get("ODDS_API_KEY")
        if not api_key:
            st.error("Missing API Key.")
        else:
            required_sport_codes = set()
            for p in st.session_state.promo_queue:
                required_sport_codes.update(SPORT_MAP[p['Sport']])
            
            cached_data = {}
            for sport_code in required_sport_codes:
                with st.spinner(f"Fetching {sport_code}..."):
                    url = f"https://api.the-odds-api.com/v4/sports/{sport_code}/odds/"
                    params = {
                        'apiKey': api_key, 'regions': 'us,us2', 'markets': 'h2h',
                        'oddsFormat': 'american', 'bookmakers': ",".join(VALID_API_KEYS)
                    }
                    try:
                        res = requests.get(url, params=params)
                        if res.status_code == 200: cached_data[sport_code] = res.json()
                    except: continue

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
                        s_target = VALID_API_KEYS if promo['Source'] == "All" else [BOOK_MAP[promo['Source']]]
                        h_target = VALID_API_KEYS if promo['Hedge'] == "All" else [BOOK_MAP[promo['Hedge']]]
                        
                        for bm in game['bookmakers']:
                            if bm['key'] in s_target:
                                for out in bm['markets'][0]['outcomes']:
                                    source_prices.append({'team': out['name'], 'price': out['price'], 'book': bm['title'], 'key': bm['key']})
                            if bm['key'] in h_target:
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
                                        "strategy_full": promo['Strategy'], "source_full": promo['Source'],
                                        "hedge_full": promo['Hedge'], "sport_full": promo['Sport'],
                                        "wager_full": promo['Wager'], "boost_full": promo['Boost'],
                                        "game": f"{game['away_team']} vs {game['home_team']}",
                                        "profit": profit, "roi": roi, "h_wager": h_wag,
                                        "s_team": s['team'], "s_price": s['price'], "s_book": s['book'],
                                        "h_team": best_h['team'], "h_price": best_h['price'], "h_book": best_h['book']
                                    })
                all_found.extend(sorted(promo_matches, key=lambda x: x['roi'], reverse=True)[:3])
            st.session_state.results = all_found

# --- 3. RESULTS ---
if st.session_state.results:
    st.markdown("---")
    grouped = {}
    for res in st.session_state.results:
        if res['promo_id'] not in grouped: grouped[res['promo_id']] = []
        grouped[res['promo_id']].append(res)

    for promo_name, matches in grouped.items():
        st.markdown(f'<div class="promo-header">🏆 Top Results: {promo_name}</div>', unsafe_allow_html=True)
        num_matches = len(matches)
        cols = st.columns(num_matches if num_matches > 0 else 1)
        for i, match in enumerate(matches):
            with cols[i]:
                with st.container(border=True):
                    st.markdown(f"**{match['game']}**")
                    st.success(f"Profit: **${match['profit']:.2f}** ({match['roi']:.1f}%)")
                    st.markdown('<p class="detail-label">Strategy / Market</p>', unsafe_allow_html=True)
                    st.markdown(f'<p class="detail-value">{match["strategy_full"]} | {match["sport_full"]}</p>', unsafe_allow_html=True)
                    st.info(f"**Bet {match['s_team']}**\n\n{match['s_book']} | {match['s_price']} | Wager: ${match['wager_full']:.0f}")
                    st.warning(f"**Bet {match['h_team']}**\n\n{match['h_book']} | {match['h_price']} | Wager: ${match['h_wager']:.2f}")

if st.session_state.results:
    if st.button("Clear Results & Queue"):
        st.session_state.promo_queue = []
        st.session_state.results = []
        st.rerun()
