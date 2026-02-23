import streamlit as st
import requests
from datetime import datetime, timezone, timedelta

# --- PAGE CONFIG ---
st.set_page_config(page_title="Arb Terminal | H2H Pro", layout="wide")

# --- CUSTOM CSS ---
st.markdown("""
    <style>
    .stApp { background-color: #f8f9fb; }
    div[data-testid="stExpander"] { background-color: white; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; border: 1px solid #eee; }
    
    /* Remove the +/- spinners from number inputs */
    input[type=number]::-webkit-inner-spin-button, 
    input[type=number]::-webkit-outer-spin-button {
        -webkit-appearance: none;
        margin: 0;
    }
    input[type=number] {
        -moz-appearance: textfield;
    }
    </style>
    """, unsafe_allow_html=True)

# --- HELPER FUNCTIONS ---
def convert_american_to_decimal(american_odds):
    if american_odds > 0:
        return (american_odds / 100) + 1
    else:
        return (100 / abs(american_odds)) + 1

# --- TITLE ---
st.title("📉 Two-Way Market Optimizer (No Ties)")
quota_placeholder = st.empty()

# --- BOOK CONFIGURATION ---
BOOK_MAP = {
    "FanDuel": "fanduel",
    "DraftKings": "draftkings",
    "theScore Bet": "espnbet",
    "Bet365": "bet365",
    "BetMGM": "betmgm",
    "Caesars": "williamhill_us",
    "Fanatics": "fanatics"
}
ALLOWED_BOOKS = list(BOOK_MAP.keys())

# --- INPUT PANEL ---
with st.sidebar:
    st.header("Search Settings")
    with st.form("settings"):
        promo_type = st.selectbox("Strategy", ["Profit Boost (%)", "Bonus Bet", "No-Sweat Bet", "Standard Arb"])
        
        max_wager = st.number_input("Source Wager ($)", value=50.0, step=None)
        
        boost_val = 0
        if promo_type == "Profit Boost (%)":
            boost_val = st.number_input("Boost Percentage (%)", value=50, step=None)
            
        source_book_name = st.selectbox("Source Book", ALLOWED_BOOKS)
        hedge_filter_name = st.selectbox("Hedge Filter", ["All Other Books"] + ALLOWED_BOOKS)
        
        # CATEGORIES EXCLUDING TIE-PRONE SPORTS
        sport_cat = st.selectbox("Sport Category", [
            "All H2H Sports", "NBA", "NHL", "MLB", "UFC / MMA", "Tennis", "NCAAB"
        ])
        
        min_roi = st.slider("Min ROI %", -2.0, 20.0, 0.0)
        
        run_scan = st.form_submit_button("Run Live Scan", use_container_width=True)

# --- SCANNER LOGIC ---
if run_scan:
    api_key = st.secrets.get("ODDS_API_KEY")
    if not api_key:
        st.error("Please add your API Key (ODDS_API_KEY) to Streamlit Secrets.")
    else:
        now = datetime.now(timezone.utc)
        source_book_key = BOOK_MAP[source_book_name]
        
        # Sport Map excluding Soccer/Tie-prone sports
        sport_map = {
            "NBA": ["basketball_nba"],
            "NHL": ["icehockey_nhl"],
            "MLB": ["baseball_mlb"],
            "UFC / MMA": ["mma_mixed_martial_arts"],
            "Tennis": ["tennis_atp_aus_open", "tennis_atp_french_open", "tennis_atp_wimbledon", "tennis_atp_us_open"],
            "NCAAB": ["basketball_ncaab"],
            "All H2H Sports": ["basketball_nba", "icehockey_nhl", "baseball_mlb", "mma_mixed_martial_arts", "basketball_ncaab"]
        }
        
        target_sports = sport_map.get(sport_cat, [])
        all_opps = []

        with st.spinner(f"Scanning upcoming {sport_cat} matches..."):
            for sport in target_sports:
                # STRICTLY using 'h2h' market to avoid 3-way (Draw) outcomes
                url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
                params = {
                    'apiKey': api_key, 
                    'regions': 'us', 
                    'markets': 'h2h', 
                    'oddsFormat': 'american'
                }
                
                try:
                    res = requests.get(url, params=params)
                    if res.status_code == 200:
                        data = res.json()
                        quota_placeholder.info(f"API Quota Remaining: {res.headers.get('x-requests-remaining')}")
                        
                        for game in data:
                            g_time = datetime.fromisoformat(game['commence_time'].replace('Z', '+00:00'))
                            
                            # Filter: Future games only (2 min buffer)
                            if g_time < now + timedelta(minutes=2): 
                                continue 
                            
                            source_prices, hedge_prices = [], []
                            
                            for bm in game['bookmakers']:
                                if bm['key'] == source_book_key:
                                    # Ensure we only grab outcomes from the h2h market
                                    for market in bm['markets']:
                                        if market['key'] == 'h2h':
                                            for out in market['outcomes']:
                                                source_prices.append({'team': out['name'], 'price': out['price'], 'book': bm['title'], 'key': bm['key']})
                                
                                elif (hedge_filter_name == "All Other Books" and bm['key'] in BOOK_MAP.values()) or (bm['key'] == BOOK_MAP.get(hedge_filter_name)):
                                    for market in bm['markets']:
                                        if market['key'] == 'h2h':
                                            for out in market['outcomes']:
                                                hedge_prices.append({'team': out['name'], 'price': out['price'], 'book': bm['title'], 'key': bm['key']})

                            # Math Logic
                            for s in source_prices:
                                best_h = None
                                for h in hedge_prices:
                                    if h['team'] != s['team'] and h['key'] != s['key']:
                                        if not best_h or h['price'] > best_h['price']:
                                            best_h = h
                                
                                if best_h:
                                    s_dec = convert_american_to_decimal(s['price'])
                                    h_dec = convert_american_to_decimal(best_h['price'])
                                    
                                    if promo_type == "Profit Boost (%)":
                                        boost_mult = 1 + (boost_val / 100)
                                        s_dec_boosted = 1 + ((s_dec - 1) * boost_mult)
                                        h_wager = (max_wager * s_dec_boosted) / h_dec
                                        profit = (max_wager * s_dec_boosted) - (max_wager + h_wager)
                                    elif promo_type == "Bonus Bet":
                                        s_dec_bonus = s_dec - 1
                                        h_wager = (max_wager * s_dec_bonus) / h_dec
                                        profit = (max_wager * s_dec_bonus) - h_wager
                                    elif promo_type == "No-Sweat Bet":
                                        # Standard 70% conversion assumption
                                        h_wager = (max_wager * (s_dec - 0.3)) / h_dec
                                        profit = (max_wager * (s_dec - 1)) - h_wager
                                    else: # Standard Arb
                                        h_wager = (max_wager * s_dec) / h_dec
                                        profit = (max_wager * s_dec) - (max_wager + h_wager)

                                    roi = (profit / max_wager) * 100
                                    if roi >= min_roi:
                                        all_opps.append({
                                            "sport": sport.upper().replace('_', ' '),
                                            "game": f"{game['away_team']} vs {game['home_team']}",
                                            "time": g_time.strftime("%m/%d %I:%M %p"),
                                            "profit": profit, "roi": roi,
                                            "s_team": s['team'], "s_price": s['price'], "s_book": s['book'],
                                            "h_team": best_h['team'], "h_price": best_h['price'], "h_book": best_h['book'],
                                            "h_wager": h_wager
                                        })
                except: continue

        # --- DISPLAY ---
        if not all_opps:
            st.warning("No future two-way opportunities found.")
        else:
            sorted_opps = sorted(all_opps, key=lambda x: x['roi'], reverse=True)
            st.subheader("🔥 Top 3 H2H Opportunities")
            for i, op in enumerate(sorted_opps[:3]):
                with st.expander(f"⭐ #{i+1} | {op['sport']} | {op['game']} | ROI: {op['roi']:.1f}%"):
                    c1, c2, c3 = st.columns(3)
                    c1.metric(f"Source: {op['s_book']}", f"{op['s_price']}", f"Bet ${max_wager:.0f}")
                    c2.metric(f"Hedge: {op['h_book']}", f"{op['h_price']}", f"Bet ${op['h_wager']:.2f}")
                    c3.metric("Profit", f"${op['profit']:.2f}", f"{op['roi']:.1f}% ROI")
                    st.caption(f"Starts: {op['time']}")
            
            if len(sorted_opps) > 3:
                st.write("---")
                for op in sorted_opps[3:]:
                    with st.expander(f"{op['sport']} | {op['game']} | ROI: {op['roi']:.1f}%"):
                        st.write(f"**{op['s_book']}** {op['s_price']:+} vs **{op['h_book']}** {op['h_price']:+}")
                        st.write(f"Bet **${max_wager:.0f}** / **${op['h_wager']:.2f}** | Profit: **${op['profit']:.2f}**")
