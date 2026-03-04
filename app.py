import streamlit as st
import requests
from datetime import datetime, timezone, timedelta

# --- PAGE CONFIG ---
st.set_page_config(page_title="Sportsbook Moneymaker", layout="wide", initial_sidebar_state="collapsed")

# --- CUSTOM CSS ---
st.markdown("""
    <style>
    [data-testid="stSidebar"] { display: none; }
    [data-testid="collapsedControl"] { display: none; }
    .stApp { background-color: #f8f9fb; }
    
    /* Result Cards */
    div[data-testid="stExpander"] { background-color: white; border-radius: 10px; border: 1px solid #ddd; margin-bottom: 15px; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; border: 1px solid #eee; }
    
    /* Clean Inputs */
    input[type=number]::-webkit-inner-spin-button, 
    input[type=number]::-webkit-outer-spin-button { -webkit-appearance: none; margin: 0; }
    input[type=number] { -moz-appearance: textfield; }

    /* Hedge Brackets */
    .hedge-header { padding: 12px; border-radius: 5px; margin-top: 25px; margin-bottom: 12px; font-weight: bold; font-size: 1.2rem; }
    .low-hedge { background-color: #e8f5e9; color: #1b5e20; border-left: 6px solid #2e7d32; }
    .med-hedge { background-color: #fff3e0; color: #e65100; border-left: 6px solid #ef6c00; }
    .high-hedge { background-color: #efebe9; color: #3e2723; border-left: 6px solid #4e342e; }
    
    .manual-calc { background-color: #ffffff; padding: 25px; border-radius: 15px; border: 2px solid #31333f; margin-top: 50px; }
    </style>
    """, unsafe_allow_html=True)

# --- HELPERS ---
def convert_american_to_decimal(american_odds):
    return (american_odds / 100) + 1 if american_odds > 0 else (100 / abs(american_odds)) + 1

BOOK_MAP = {
    "All": "all", "theScore Bet": "espnbet", "FanDuel": "fanduel", "DraftKings": "draftkings",
    "Bet365": "bet365", "BetMGM": "betmgm", "Caesars": "williamhill_us", "Fanatics": "fanatics"
}
VALID_BOOKS = [v for k, v in BOOK_MAP.items() if v != "all"]

# --- TITLE ---
st.title("💰 Sportsbook Moneymaker")

# --- MAIN INPUT PANEL ---
with st.container():
    r1c1, r1c2, r1c3, r1c4 = st.columns(4)
    with r1c1: promo_type = st.selectbox("Strategy", ["Profit Boost (%)", "Bonus Bet", "No-Sweat Bet", "Standard Arb"])
    with r1c2: max_wager = st.number_input("Source Wager ($)", value=50.0, step=None)
    with r1c3: source_book_name = st.selectbox("Source Book", list(BOOK_MAP.keys()), index=0)
    with r1c4: hedge_book_name = st.selectbox("Hedge Book", list(BOOK_MAP.keys()), index=0)

    r2c1, r2c2, r2c3, r2c4 = st.columns([1, 1, 1, 1])
    with r2c1: boost_val = st.number_input("Boost %", value=50, step=None) if promo_type == "Profit Boost (%)" else 0
    with r2c2: sport_cat = st.selectbox("Sport Category", ["All H2H Sports", "NBA", "NHL", "MLB", "UFC / MMA", "Tennis", "NCAAB"])
    with r2c3: debug_mode = st.toggle("Debug Mode", value=False)
    with r2c4: 
        st.write("")
        run_scan = st.button("🚀 Run Live Scan", use_container_width=True)

# --- SCANNER LOGIC ---
best_match_for_calc = None

if run_scan:
    api_key = st.secrets.get("ODDS_API_KEY")
    if not api_key:
        st.error("Please add your API Key to Streamlit Secrets.")
    else:
        now = datetime.now(timezone.utc)
        
        request_books = set()
        if source_book_name == "All": request_books.update(VALID_BOOKS)
        else: request_books.add(BOOK_MAP[source_book_name])
        if hedge_book_name == "All": request_books.update(VALID_BOOKS)
        else: request_books.add(BOOK_MAP[hedge_book_name])
        bookmaker_query = ",".join(request_books)

        # --- UPDATED SPORT MAP: FULL 2026 ATP/WTA CALENDAR ---
        sport_map = {
            "NBA": ["basketball_nba"], 
            "NHL": ["icehockey_nhl"], 
            "MLB": ["baseball_mlb"], 
            "UFC / MMA": ["mma_mixed_martial_arts"],
            "Tennis": [
                # Current & Upcoming Masters 1000s
                "tennis_atp_indian_wells", "tennis_wta_indian_wells",
                "tennis_atp_miami_open", "tennis_wta_miami_open",
                "tennis_atp_monte_carlo_masters",
                "tennis_atp_madrid_open", "tennis_wta_madrid_open",
                "tennis_atp_italian_open", "tennis_wta_italian_open",
                "tennis_atp_canadian_open", "tennis_wta_canadian_open",
                "tennis_atp_cincinnati_open", "tennis_wta_cincinnati_open",
                "tennis_atp_shanghai_masters",
                "tennis_atp_paris_masters",
                
                # Grand Slams
                "tennis_atp_aus_open", "tennis_wta_aus_open",
                "tennis_atp_french_open", "tennis_wta_french_open",
                "tennis_atp_wimbledon", "tennis_wta_wimbledon",
                "tennis_atp_us_open", "tennis_wta_us_open",
                
                # Season Finals & Combined
                "tennis_atp_finals",
                "tennis_atp_combined", "tennis_wta_combined"
            ],
            "NCAAB": ["basketball_ncaab"],
            "All H2H Sports": [
                "basketball_nba", "icehockey_nhl", "baseball_mlb", 
                "tennis_atp_indian_wells", "tennis_atp_miami_open", "basketball_ncaab"
            ]
        }
        target_sports = sport_map.get(sport_cat, [])
        all_opps = []

        with st.spinner(f"Scanning {len(request_books)} books..."):
            for sport in target_sports:
                url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
                params = {'apiKey': api_key, 'regions': 'us', 'markets': 'h2h', 'oddsFormat': 'american', 'bookmakers': bookmaker_query}
                try:
                    res = requests.get(url, params=params)
                    if res.status_code == 200:
                        data = res.json()
                        for game in data:
                            g_time = datetime.fromisoformat(game['commence_time'].replace('Z', '+00:00'))
                            if g_time < now + timedelta(minutes=2): continue 
                            
                            source_prices, hedge_prices = [], []
                            for bm in game['bookmakers']:
                                s_key, h_key = BOOK_MAP[source_book_name], BOOK_MAP[hedge_book_name]
                                if s_key == "all" or bm['key'] == s_key:
                                    for out in bm['markets'][0]['outcomes']:
                                        source_prices.append({'team': out['name'], 'price': out['price'], 'book': bm['title'], 'key': bm['key']})
                                if h_key == "all" or bm['key'] == h_key:
                                    for out in bm['markets'][0]['outcomes']:
                                        hedge_prices.append({'team': out['name'], 'price': out['price'], 'book': bm['title'], 'key': bm['key']})

                            for s in source_prices:
                                best_h = None
                                for h in hedge_prices:
                                    if h['team'] != s['team'] and h['key'] != s['key']:
                                        if not best_h or h['price'] > best_h['price']: best_h = h
                                
                                if best_h:
                                    s_dec, h_dec = convert_american_to_decimal(s['price']), convert_american_to_decimal(best_h['price'])
                                    if promo_type == "Profit Boost (%)":
                                        ms_dec_b = 1 + ((s_dec - 1) * (1 + (boost_val / 100)))
                                        h_wager = (max_wager * ms_dec_b) / h_dec
                                        profit = (max_wager * ms_dec_b) - (max_wager + h_wager)
                                    elif promo_type == "Bonus Bet":
                                        h_wager = (max_wager * (s_dec - 1)) / h_dec
                                        profit = (max_wager * (s_dec - 1)) - h_wager
                                    elif promo_type == "No-Sweat Bet":
                                        h_wager = (max_wager * (s_dec - 0.3)) / h_dec
                                        profit = (max_wager * (s_dec - 1)) - h_wager
                                    else:
                                        h_wager = (max_wager * s_dec) / h_dec
                                        profit = (max_wager * s_dec) - (max_wager + h_wager)

                                    roi = (profit / max_wager) * 100
                                    if roi >= -10:
                                        opp = {
                                            "sport": sport.upper().replace('_', ' '), "game": f"{game['away_team']} vs {game['home_team']}",
                                            "time": g_time.strftime("%m/%d %I:%M %p"), "profit": profit, "roi": roi,
                                            "s_team": s['team'], "s_price": s['price'], "s_book": s['book'],
                                            "h_team": best_h['team'], "h_price": best_h['price'], "h_book": best_h['book'],
                                            "h_wager": h_wager
                                        }
                                        all_opps.append(opp)
                                        if best_match_for_calc is None or roi > best_match_for_calc['roi']:
                                            best_match_for_calc = opp
                except: continue

        if not all_opps: st.warning("No live opportunities found for the selected sports.")
        else:
            # Display logic
            low = sorted([o for o in all_opps if o['h_wager'] < 50], key=lambda x: x['roi'], reverse=True)[:3]
            med = sorted([o for o in all_opps if 50 <= o['h_wager'] < 150], key=lambda x: x['roi'], reverse=True)[:3]
            hi = sorted([o for o in all_opps if o['h_wager'] >= 150], key=lambda x: x['roi'], reverse=True)[:3]
            for title, data, css in [("🟢 Low Hedge", low, "low-hedge"), ("🟠 Medium Hedge", med, "med-hedge"), ("🔴 High Hedge", hi, "high-hedge")]:
                if data:
                    st.markdown(f'<div class="hedge-header {css}">{title}</div>', unsafe_allow_html=True)
                    for op in data:
                        label = f"💰 **+${op['profit']:.2f}** ({op['roi']:.1f}% ROI) — {op['game']} "
                        with st.expander(label):
                            st.markdown(f"**Game Time:** {op['time']} | **Sport:** {op['sport']}")
                            c1, c2 = st.columns(2)
                            with c1:
                                st.info(f"👉 **BET ON: {op['s_team']}**")
                                st.metric(f"Source: {op['s_book']}", f"{op['s_price']}", f"Wager: ${max_wager:.0f}")
                            with c2:
                                st.warning(f"👉 **BET ON: {op['h_team']}**")
                                st.metric(f"Hedge: {op['h_book']}", f"{op['h_price']}", f"Wager: ${op['h_wager']:.2f}")

# --- MANUAL CALCULATOR ---
st.markdown('<div class="manual-calc">', unsafe_allow_html=True)
st.subheader("🖋️ Manual Adjustment Calculator")
d_st, d_sp, d_hp = (best_match_for_calc['s_team'], best_match_for_calc['s_price'], best_match_for_calc['h_price']) if best_match_for_calc else ("Team A", 100, -110)
mc1, mc2, mc3 = st.columns(3)
with mc1: 
    m_wag = st.number_input("Manual Wager ($)", value=max_wager, key="mw")
    m_bst = st.number_input("Manual Boost %", value=float(boost_val), key="mb")
with mc2: m_sp = st.number_input(f"Source Odds", value=float(d_sp), key="msp")
with mc3: m_hp = st.number_input("Hedge Odds", value=float(d_hp), key="mhp")

ms_d, mh_d = convert_american_to_decimal(m_sp), convert_american_to_decimal(m_hp)
if promo_type == "Profit Boost (%)":
    ms_db = 1 + ((ms_d - 1) * (1 + (m_bst / 100)))
    mh_wag = (m_wag * ms_db) / mh_d
    m_prof = (m_wag * ms_db) - (m_wag + mh_wag)
elif promo_type == "Bonus Bet":
    mh_wag = (m_wag * (ms_d - 1)) / mh_d
    m_prof = (m_wag * (ms_d - 1)) - mh_wag
else: 
    mh_wag = (m_wag * ms_d) / mh_d
    m_prof = (m_wag * ms_d) - (m_wag + mh_wag)

st.markdown("---")
r1, r2, r3 = st.columns(3)
r1.metric("Required Hedge", f"${mh_wag:.2f}")
r2.metric("Manual Profit", f"${m_prof:.2f}")
r3.metric("Manual ROI", f"{(m_prof/m_wag)*100:.1f}%")
st.markdown('</div>', unsafe_allow_html=True)
