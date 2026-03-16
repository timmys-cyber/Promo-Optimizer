import streamlit as st
import requests
from datetime import datetime, timezone, timedelta

# --- PAGE CONFIG ---
st.set_page_config(page_title="Sportsbook Pro Optimizer", layout="wide")

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
    .queue-container { background-color: #ffffff; padding: 20px; border-radius: 12px; border: 1px solid #e0e0e0; }
    .promo-tag { background-color: #f1f3f6; padding: 4px 8px; border-radius: 4px; font-weight: bold; font-size: 0.85rem; color: #31333F; }
    .stMetric { border: 1px solid #f0f0f0; padding: 10px; border-radius: 8px; }
    </style>
    """, unsafe_allow_html=True)

st.title("💰 Multi-Promo Optimizer")

# --- 1. PROMO INPUT ---
with st.container():
    c1, c2, c3, c4 = st.columns(4)
    with c1: p_type = st.selectbox("Strategy", ["Profit Boost (%)", "Bonus Bet", "No-Sweat Bet", "Standard Arb"])
    with c2: p_wager = st.number_input("Wager ($)", value=50.0, step=5.0)
    with c3: p_source = st.selectbox("Source Book", list(BOOK_MAP.keys()), index=1)
    with c4: p_hedge = st.selectbox("Hedge Book", list(BOOK_MAP.keys()), index=0)

    c2_1, c2_2, c2_3 = st.columns([1, 1, 1])
    with c2_1: 
        p_boost = st.number_input("Boost %", value=50) if p_type == "Profit Boost (%)" else 0
    with c2_2: 
        p_sport = st.selectbox("Sport Category", list(SPORT_MAP.keys()))
    with c2_3:
        st.write("")
        if st.button("➕ Add Promo to Queue", use_container_width=True, type="secondary"):
            st.session_state.promo_queue.append({
                "type": p_type, "wager": p_wager, "source": p_source, 
                "hedge": p_hedge, "boost": p_boost, "sport": p_sport
            })
            st.rerun()

# --- 2. DISPLAY QUEUE ---
if st.session_state.promo_queue:
    st.markdown("### 📋 Pending Promo Queue")
    
    # Summary Metric
    total_wager = sum([p['wager'] for p in st.session_state.promo_queue])
    st.caption(f"Total Bankroll Required for Source Bets: **${total_wager:.2f}**")

    for idx, p in enumerate(st.session_state.promo_queue):
        with st.container():
            col_a, col_b = st.columns([0.85, 0.15])
            
            # Formatting the boost string
            boost_str = f" | {p['boost']}% Boost" if p['type'] == "Profit Boost (%)" else ""
            
            col_a.markdown(
                f"""
                **{p['source']}** <span class="promo-tag">{p['type']}</span>  
                **Wager:** ${p['wager']:.2f}{boost_str} | **Sport:** {p['sport']}
                """, unsafe_allow_html=True
            )
            
            if col_b.button("🗑️", key=f"rm_{idx}"):
                st.session_state.promo_queue.pop(idx)
                st.rerun()
        st.divider()

    # --- SCAN LOGIC ---
    if st.button("🚀 SCAN ALL QUEUED PROMOS", type="primary", use_container_width=True):
        api_key = st.secrets.get("ODDS_API_KEY")
        if not api_key:
            st.error("Missing API Key.")
        else:
            required_sport_codes = set()
            for promo in st.session_state.promo_queue:
                required_sport_codes.update(SPORT_MAP[promo['sport']])
            
            cached_data = {}
            for sport_code in required_sport_codes:
                with st.spinner(f"Fetching {sport_code} odds..."):
                    url = f"https://api.the-odds-api.com/v4/sports/{sport_code}/odds/"
                    params = {'apiKey': api_key, 'regions': 'us', 'markets': 'h2h', 'oddsFormat': 'american'}
                    res = requests.get(url, params=params)
                    if res.status_code == 200:
                        cached_data[sport_code] = res.json()

            found_opps = []
            now = datetime.now(timezone.utc)
            
            for promo in st.session_state.promo_queue:
                target_codes = SPORT_MAP[promo['sport']]
                for code in target_codes:
                    if code not in cached_data: continue
                    for game in cached_data[code]:
                        g_time = datetime.fromisoformat(game['commence_time'].replace('Z', '+00:00'))
                        if g_time < now + timedelta(minutes=2): continue
                        
                        source_prices, hedge_prices = [], []
                        s_key, h_key = BOOK_MAP[promo['source']], BOOK_MAP[promo['hedge']]
                        
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
                                
                                if promo['type'] == "Profit Boost (%)":
                                    boosted_s = 1 + ((s_dec - 1) * (1 + (promo['boost'] / 100)))
                                    h_wag = (promo['wager'] * boosted_s) / h_dec
                                    profit = (promo['wager'] * boosted_s) - (promo['wager'] + h_wag)
                                elif promo['type'] == "Bonus Bet":
                                    h_wag = (promo['wager'] * (s_dec - 1)) / h_dec
                                    profit = (promo['wager'] * (s_dec - 1)) - h_wag
                                else:
                                    h_wag = (promo['wager'] * s_dec) / h_dec
                                    profit = (promo['wager'] * s_dec) - (promo['wager'] + h_wag)

                                roi = (profit / promo['wager']) * 100
                                if roi >= -12:
                                    found_opps.append({
                                        "label": f"{promo['source']} {promo['type']}",
                                        "game": f"{game['away_team']} vs {game['home_team']}",
                                        "profit": profit, "roi": roi, "h_wager": h_wag,
                                        "s_team": s['team'], "s_price": s['price'], "s_book": s['book'],
                                        "h_team": best_h['team'], "h_price": best_h['price'], "h_book": best_h['book']
                                    })
            st.session_state.results = found_opps

# --- 3. DISPLAY RESULTS ---
if st.session_state.results:
    st.markdown("---")
    st.subheader(f"🎯 Top Opportunities ({len(st.session_state.results)})")
    for op in sorted(st.session_state.results, key=lambda x: x['roi'], reverse=True):
        with st.expander(f"💰 +${op['profit']:.2f} ({op['roi']:.1f}% ROI) | {op['label']} | {op['game']}"):
            res_c1, res_c2 = st.columns(2)
            res_c1.info(f"**Bet {op['s_team']}**\n\nBook: {op['s_book']} | Odds: {op['s_price']}")
            res_c2.warning(f"**Bet {op['h_team']}**\n\nBook: {op['h_book']} | Odds: {op['h_price']} | **Hedge: ${op['h_wager']:.2f}**")

if st.button("Reset Everything", type="primary"):
    st.session_state.promo_queue = []
    st.session_state.results = []
    st.rerun()
