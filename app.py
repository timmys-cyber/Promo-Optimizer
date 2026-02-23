import streamlit as st
import requests
from datetime import datetime, timezone, timedelta

# --- PAGE CONFIG ---
st.set_page_config(page_title="Arb Terminal | H2H Pro", layout="wide", initial_sidebar_state="collapsed")

# --- CUSTOM CSS ---
st.markdown("""
    <style>
    /* Permanently hide the sidebar and menu items for a cleaner look */
    [data-testid="stSidebar"] { display: none; }
    [data-testid="collapsedControl"] { display: none; }
    
    .stApp { background-color: #f8f9fb; }
    div[data-testid="stExpander"] { background-color: white; border-radius: 10px; border: 1px solid #eee; margin-bottom: 15px; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; border: 1px solid #eee; }
    
    /* Remove number input +/- buttons */
    input[type=number]::-webkit-inner-spin-button, 
    input[type=number]::-webkit-outer-spin-button { -webkit-appearance: none; margin: 0; }
    input[type=number] { -moz-appearance: textfield; }
    
    .hedge-header { padding: 10px; border-radius: 5px; margin-top: 20px; margin-bottom: 10px; font-weight: bold; font-size: 1.1rem; }
    .low-hedge { background-color: #e8f5e9; color: #2e7d32; border-left: 5px solid #2e7d32; }
    .med-hedge { background-color: #fff3e0; color: #ef6c00; border-left: 5px solid #ef6c00; }
    .high-hedge { background-color: #efebe9; color: #4e342e; border-left: 5px solid #4e342e; }
    </style>
    """, unsafe_allow_html=True)

# --- HELPER FUNCTIONS ---
def convert_american_to_decimal(american_odds):
    return (american_odds / 100) + 1 if american_odds > 0 else (100 / abs(american_odds)) + 1

# --- TITLE ---
st.title("📈 Top-3 Two-Way Optimizer")

# --- MAIN INPUT PANEL ---
with st.container():
    # Top Row for Settings
    row1_c1, row1_c2, row1_c3, row1_c4 = st.columns(4)
    with row1_c1:
        promo_type = st.selectbox("Strategy", ["Profit Boost (%)", "Bonus Bet", "No-Sweat Bet", "Standard Arb"])
    with row1_c2:
        max_wager = st.number_input("Source Wager ($)", value=50.0, step=None)
    with row1_c3:
        source_book_name = st.selectbox("Source Book", ["FanDuel", "DraftKings", "theScore Bet", "Bet365", "BetMGM", "Caesars", "Fanatics"])
    with row1_c4:
        sport_cat = st.selectbox("Sport Category", ["All H2H Sports", "NBA", "NHL", "MLB", "UFC / MMA", "Tennis", "NCAAB"])

    # Bottom Row for Filters & Execution
    row2_c1, row2_c2, row2_c3 = st.columns([1, 1, 2])
    with row2_c1:
        boost_val = st.number_input("Boost %", value=50, step=None) if promo_type == "Profit Boost (%)" else 0
    with row2_c2:
        min_roi = st.slider("Min ROI %", -2.0, 20.0, 0.0)
    with row2_c3:
        st.write("") # Spacer
        run_scan = st.button("🚀 Run Live Scan", use_container_width=True)

# --- SCANNER LOGIC ---
if run_scan:
    api_key = st.secrets.get("ODDS_API_KEY")
    if not api_key:
        st.error("Please add your API Key to Streamlit Secrets.")
    else:
        now = datetime.now(timezone.utc)
        BOOK_MAP = {"FanDuel": "fanduel", "DraftKings": "draftkings", "theScore Bet": "espnbet", "Bet365": "bet365", "BetMGM": "betmgm", "Caesars": "williamhill_us", "Fanatics": "fanatics"}
        source_book_key = BOOK_MAP[source_book_name]
        
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
                                if bm['key'] == source_book_key:
                                    for market in bm['markets']:
                                        if market['key'] == 'h2h':
                                            for out in market['outcomes']:
                                                source_prices.append({'team': out['name'], 'price': out['price'], 'book': bm['title'], 'key': bm['key']})
                                elif bm['key'] != source_book_key and bm['key'] in BOOK_MAP.values():
                                    for market in bm['markets']:
                                        if market['key'] == 'h2h':
                                            for out in market['outcomes']:
                                                hedge_prices.append({'team': out['name'], 'price': out['price'], 'book': bm['title'], 'key': bm['key']})

                            for s in source_prices:
                                best_h = None
                                for h in hedge_prices:
                                    if h['team'] != s['team']:
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
                                    else: # Standard Arb
                                        h_wager = (max_wager * s_dec) / h_dec
                                        profit = (max_wager * s_dec) - (max_wager + h_wager)

                                    roi = (profit / max_wager) * 100
                                    if roi >= min_roi:
                                        all_opps.append({
                                            "sport": sport.upper().replace('_', ' '), "game": f"{game['away_team']} vs {game['home_team']}",
                                            "time": g_time.strftime("%m/%d %I:%M %p"), "profit": profit, "roi": roi,
                                            "s_team": s['team'], "s_price": s['price'], "s_book": s['book'],
                                            "h_team": best_h['team'], "h_price": best_h['price'], "h_book": best_h['book'],
                                            "h_wager": h_wager
                                        })
                except: continue

        # --- DISPLAY TOP 3 PER GROUP ---
        if not all_opps:
            st.warning("No opportunities found matching these criteria.")
        else:
            # Grouping Logic
            low_hedge = sorted([o for o in all_opps if o['h_wager'] < 50], key=lambda x: x['roi'], reverse=True)[:3]
            med_hedge = sorted([o for o in all_opps if 50 <= o['h_wager'] < 150], key=lambda x: x['roi'], reverse=True)[:3]
            high_hedge = sorted([o for o in all_opps if o['h_wager'] >= 150], key=lambda x: x['roi'], reverse=True)[:3]

            groups = [
                ("🟢 Top 3: Low Hedge (< $50)", low_hedge, "low-hedge"),
                ("🟠 Top 3: Medium Hedge ($50 - $150)", med_hedge, "med-hedge"),
                ("🔴 Top 3: High Hedge (> $150)", high_hedge, "high-hedge")
            ]

            for title, data, css_class in groups:
                if data:
                    st.markdown(f'<div class="hedge-header {css_class}">{title}</div>', unsafe_allow_html=True)
                    for op in data:
                        with st.expander(f"{op['sport']} | {op['game']} | ROI: {op['roi']:.1f}%"):
                            c1, c2, c3 = st.columns(3)
                            c1.metric(f"Source: {op['s_book']}", f"{op['s_price']:+}", f"Bet ${max_wager:.0f}")
                            c2.metric(f"Hedge: {op['h_book']}", f"{op['h_price']:+}", f"Bet ${op['h_wager']:.2f}")
                            c3.metric("Profit", f"${op['profit']:.2f}", f"{op['roi']:.1f}% ROI")
                            st.caption(f"Starts: {op['time']}")
