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
    div[data-testid="stExpander"] { background-color: white; border-radius: 10px; border: 1px solid #eee; margin-bottom: 15px; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; border: 1px solid #eee; }
    
    input[type=number]::-webkit-inner-spin-button, 
    input[type=number]::-webkit-outer-spin-button { -webkit-appearance: none; margin: 0; }
    input[type=number] { -moz-appearance: textfield; }

    .hedge-header { padding: 10px; border-radius: 5px; margin-top: 20px; margin-bottom: 10px; font-weight: bold; font-size: 1.1rem; }
    .low-hedge { background-color: #e8f5e9; color: #2e7d32; border-left: 5px solid #2e7d32; }
    .med-hedge { background-color: #fff3e0; color: #ef6c00; border-left: 5px solid #ef6c00; }
    .high-hedge { background-color: #efebe9; color: #4e342e; border-left: 5px solid #4e342e; }
    
    .manual-calc { background-color: #ffffff; padding: 25px; border-radius: 15px; border: 2px solid #31333f; margin-top: 50px; }
    </style>
    """, unsafe_allow_html=True)

# --- HELPERS ---
def convert_american_to_decimal(american_odds):
    return (american_odds / 100) + 1 if american_odds > 0 else (100 / abs(american_odds)) + 1

BOOK_MAP = {
    "All": "all", "FanDuel": "fanduel", "DraftKings": "draftkings", "theScore Bet": "espnbet",
    "Bet365": "bet365", "BetMGM": "betmgm", "Caesars": "williamhill_us", "Fanatics": "fanatics"
}

# --- TITLE ---
st.title("💰 Sportsbook Moneymaker")

# --- MAIN INPUT PANEL ---
with st.container():
    r1c1, r1c2, r1c3, r1c4 = st.columns(4)
    with r1c1: promo_type = st.selectbox("Strategy", ["Profit Boost (%)", "Bonus Bet", "No-Sweat Bet", "Standard Arb"])
    with r1c2: max_wager = st.number_input("Source Wager ($)", value=50.0, step=None)
    with r1c3: source_book_name = st.selectbox("Source Book", list(BOOK_MAP.keys()), index=0)
    with r1c4: hedge_book_name = st.selectbox("Hedge Book", list(BOOK_MAP.keys()), index=0)

    r2c1, r2c2, r2c3 = st.columns([1, 1, 2])
    with r2c1: boost_val = st.number_input("Boost %", value=50, step=None) if promo_type == "Profit Boost (%)" else 0
    with r2c2: sport_cat = st.selectbox("Sport Category", ["All H2H Sports", "NBA", "NHL", "MLB", "UFC / MMA", "Tennis", "NCAAB"])
    with r2c3: 
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
        sport_map = {
            "NBA": ["basketball_nba"], "NHL": ["icehockey_nhl"], "MLB": ["baseball_mlb"], "UFC / MMA": ["mma_mixed_martial_arts"],
            "Tennis": ["tennis_atp_aus_open", "tennis_atp_french_open", "tennis_atp_wimbledon", "tennis_atp_us_open"],
            "NCAAB": ["basketball_ncaab"],
            "All H2H Sports": ["basketball_nba", "icehockey_nhl", "baseball_mlb", "mma_mixed_martial_arts", "basketball_ncaab"]
        }
        target_sports = sport_map.get(sport_cat, [])
        all_opps = []

        with st.spinner("Finding highest ROI plays..."):
            for sport in target_sports:
                url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
                params = {'apiKey': api_key, 'regions': 'us', 'markets': 'h2h', 'oddsFormat': 'american'}
                try:
                    res = requests.get(url, params=params)
                    if res.status_code == 200:
                        data = res.json()
                        for game in data:
                            g_time = datetime.fromisoformat(game['commence_time'].replace('Z', '+00:00'))
                            if g_time < now + timedelta(minutes=2): continue 
                            
                            source_prices, hedge_prices = [], []
                            for bm in game['bookmakers']:
                                is_source = (source_book_name == "All" and bm['key'] in BOOK_MAP.values()) or (bm['key'] == BOOK_MAP[source_book_name])
                                is_hedge = (hedge_book_name == "All" and bm['key'] in BOOK_MAP.values()) or (bm['key'] == BOOK_MAP[hedge_book_name])
                                if is_source:
                                    for out in bm['markets'][0]['outcomes']:
                                        source_prices.append({'team': out['name'], 'price': out['price'], 'book': bm['title'], 'key': bm['key']})
                                if is_hedge:
                                    for out in bm['markets'][0]['outcomes']:
                                        hedge_prices.append({'team': out['name'], 'price': out['price'], 'book': bm['title'], 'key': bm['key']})

                            for s in source_prices:
                                best_h = None
                                for h in hedge_prices:
                                    if h['team'] != s['team'] and h['key'] != s['key']:
                                        if not best_h or h['price'] > best_h['price']: best_h = h
                                
                                if best_h:
                                    s_dec = convert_american_to_decimal(s['price'])
                                    h_dec = convert_american_to_decimal(best_h['price'])
                                    
                                    if promo_type == "Profit Boost (%)":
                                        boost_mult = 1 + (boost_val / 100)
                                        s_dec_boosted = 1 + ((s_dec - 1) * boost_mult)
                                        h_wager = (max_wager * s_dec_boosted) / h_dec
                                        profit = (max_wager * s_dec_boosted) - (max_wager + h_wager)
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

        if not all_opps:
            st.warning("No opportunities found.")
        else:
            low_hedge = sorted([o for o in all_opps if o['h_wager'] < 50], key=lambda x: x['roi'], reverse=True)[:3]
            med_hedge = sorted([o for o in all_opps if 50 <= o['h_wager'] < 150], key=lambda x: x['roi'], reverse=True)[:3]
            high_hedge = sorted([o for o in all_opps if o['h_wager'] >= 150], key=lambda x: x['roi'], reverse=True)[:3]

            groups = [("🟢 Top 3: Low Hedge", low_hedge, "low-hedge"), ("🟠 Top 3: Medium Hedge", med_hedge, "med-hedge"), ("🔴 Top 3: High Hedge", high_hedge, "high-hedge")]
            for title, data, css_class in groups:
                if data:
                    st.markdown(f'<div class="hedge-header {css_class}">{title}</div>', unsafe_allow_html=True)
                    for op in data:
                        with st.expander(f"{op['sport']} | {op['game']} | ROI: {op['roi']:.1f}%"):
                            c1, c2, c3 = st.columns(3)
                            c1.metric(f"Source: {op['s_book']}", f"{op['s_price']:+}", f"Bet ${max_wager:.0f}")
                            c2.metric(f"Hedge: {op['h_book']}", f"{op['h_price']:+}", f"Bet ${op['h_wager']:.2f}")
                            c3.metric("Profit", f"${op['profit']:.2f}", f"{op['roi']:.1f}% ROI")

# --- MANUAL CALCULATOR SECTION ---
st.markdown('<div class="manual-calc">', unsafe_allow_html=True)
st.subheader("🖋️ Manual Adjustment Calculator")
st.write("Tweak the numbers below for custom scenarios or if lines move.")

# Default values from best match if available, otherwise blank
d_s_team = best_match_for_calc['s_team'] if best_match_for_calc else "Team A"
d_s_price = best_match_for_calc['s_price'] if best_match_for_calc else 100
d_h_price = best_match_for_calc['h_price'] if best_match_for_calc else -110

mc1, mc2, mc3 = st.columns(3)
with mc1:
    m_wager = st.number_input("Manual Wager ($)", value=max_wager, step=None)
    m_boost = st.number_input("Manual Boost %", value=boost_val, step=None)
with mc2:
    m_s_price = st.number_input(f"Source Odds ({d_s_team})", value=float(d_s_price), step=None)
with mc3:
    m_h_price = st.number_input("Hedge Odds (Opponent)", value=float(d_h_price), step=None)

# Live Math for Manual Calc
ms_dec = convert_american_to_decimal(m_s_price)
mh_dec = convert_american_to_decimal(m_h_price)

if promo_type == "Profit Boost (%)":
    mb_mult = 1 + (m_boost / 100)
    ms_dec_b = 1 + ((ms_dec - 1) * mb_mult)
    mh_wager = (m_wager * ms_dec_b) / mh_dec
    m_profit = (m_wager * ms_dec_b) - (m_wager + mh_wager)
elif promo_type == "Bonus Bet":
    mh_wager = (m_wager * (ms_dec - 1)) / mh_dec
    m_profit = (m_wager * (ms_dec - 1)) - mh_wager
elif promo_type == "No-Sweat Bet":
    mh_wager = (m_wager * (ms_dec - 0.3)) / mh_dec
    m_profit = (m_wager * (ms_dec - 1)) - mh_wager
else:
    mh_wager = (m_wager * ms_dec) / mh_dec
    m_profit = (m_wager * ms_dec) - (m_wager + mh_wager)

m_roi = (m_profit / m_wager) * 100

st.markdown("---")
res1, res2, res3 = st.columns(3)
res1.metric("Required Hedge", f"${mh_wager:.2f}")
res2.metric("Manual Profit", f"${m_profit:.2f}")
res3.metric("Manual ROI", f"{m_roi:.1f}%")
st.markdown('</div>', unsafe_allow_html=True)
