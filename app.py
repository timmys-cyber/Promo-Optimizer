import streamlit as st
import requests
from datetime import datetime, timezone, timedelta

# --- PAGE CONFIG ---
st.set_page_config(page_title="Arb Terminal | Olympic Focus", layout="wide")

# --- CUSTOM CSS ---
st.markdown("""
    <style>
    .stApp { background-color: #f8f9fb; }
    div[data-testid="stExpander"] { background-color: white; border-radius: 10px; }
    .stMetric { background-color: #ffffff; padding: 10px; border-radius: 10px; border: 1px solid #eee; }
    </style>
    """, unsafe_allow_html=True)

st.title("🥇 Olympic & Pro Optimizer")
quota_placeholder = st.empty()

# --- BOOK CONFIGURATION ---
# Mapping readable names to The Odds API keys
# Note: Caesars uses 'williamhill_us', theScore Bet uses 'espnbet'
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
with st.form("settings"):
    c1, c2, c3 = st.columns(3)
    with c1:
        promo_type = st.selectbox("Strategy", ["Profit Boost (%)", "Bonus Bet", "No-Sweat Bet"])
        max_wager = st.number_input("Wager Amount ($)", value=50.0)
    with c2:
        source_book_name = st.selectbox("Source Book", ALLOWED_BOOKS)
        boost_val = st.number_input("Boost %", value=50) if promo_type == "Profit Boost (%)" else 0
    with c3:
        hedge_filter_name = st.selectbox("Hedge Filter", ["All Allowed Books"] + ALLOWED_BOOKS)
        sport_cat = st.selectbox("Sport Category", ["Olympic Hockey", "All Sports", "NBA", "NHL", "NCAAB"])

    source_book = BOOK_MAP[source_book_name]
    hedge_filter = "all" if hedge_filter_name == "All Allowed Books" else BOOK_MAP[hedge_filter_name]
    
    run_scan = st.form_submit_button("Run Full Scan", use_container_width=True)

# --- SCANNER LOGIC ---
if run_scan:
    api_key = st.secrets.get("ODDS_API_KEY")
    if not api_key:
        st.error("Missing API Key in Secrets!")
    else:
        now = datetime.now(timezone.utc)
        
        sport_map = {
            "Olympic Hockey": ["icehockey_winter_olympics", "icehockey_winter_olympics_womens"],
            "NBA": ["basketball_nba"],
            "NHL": ["icehockey_nhl"],
            "NCAAB": ["basketball_ncaab"],
            "All Sports": ["icehockey_winter_olympics", "icehockey_nhl", "basketball_nba", "basketball_ncaab"]
        }
        
        target_sports = sport_map.get(sport_cat, [])
        all_opps = []
        
        # Define the set of internal keys we care about for filtering
        allowed_keys = set(BOOK_MAP.values())

        with st.spinner(f"Searching for {sport_cat} lines..."):
            for sport in target_sports:
                for market in ["h2h", "h2h_3_way"]:
                    url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
                    params = {
                        'apiKey': api_key, 
                        'regions': 'us', 
                        'markets': market,
                        'oddsFormat': 'american'
                    }
                    
                    try:
                        res = requests.get(url, params=params)
                        if res.status_code == 200:
                            data = res.json()
                            quota_placeholder.info(f"Requests Left: {res.headers.get('x-requests-remaining')}")
                            
                            for game in data:
                                g_time = datetime.fromisoformat(game['commence_time'].replace('Z', '+00:00'))
                                if g_time < now - timedelta(hours=3): continue 
                                
                                s_odds, h_odds = [], []
                                for bm in game['bookmakers']:
                                    # Skip any book not in our allowed list
                                    if bm['key'] not in allowed_keys:
                                        continue

                                    # Identify Source Odds
                                    if bm['key'] == source_book:
                                        for m in bm['markets']:
                                            for out in m['outcomes']:
                                                s_odds.append({'team': out['name'], 'price': out['price'], 'book': bm['title']})
                                    
                                    # Identify Hedge Odds
                                    if hedge_filter == "all" or bm['key'] == hedge_filter:
                                        for m in bm['markets']:
                                            for out in m['outcomes']:
                                                h_odds.append({'team': out['name'], 'price': out['price'], 'book': bm['title']})

                                # Calculation Logic
                                for s in s_odds:
                                    best_h = None
                                    for h in h_odds:
                                        if h['team'] != s['team']:
                                            if not best_h or h['price'] > best_h['price']:
                                                best_h = h
                                    
                                    if best_h:
                                        s_m = s['price']/100 if s['price']>0 else 100/abs(s['price'])
                                        h_m = best_h['price']/100 if best_h['price']>0 else 100/abs(best_h['price'])
                                        
                                        if promo_type == "Profit Boost (%)":
                                            b_s_m = s_m * (1 + (boost_val/100))
                                            h_amt = (max_wager * (1 + b_s_m)) / (1 + h_m)
                                            profit = (max_wager * b_s_m) - h_amt
                                        elif promo_type == "Bonus Bet":
                                            h_amt = (max_wager * s_m) / (1 + h_m)
                                            profit = (max_wager * s_m) - h_amt
                                        else: # No Sweat
                                            h_amt = (max_wager * (s_m + 0.3)) / (h_m + 1)
                                            profit = (max_wager * s_m) - h_amt

                                        if profit > -10:
                                            all_opps.append({
                                                "sport": "OLYMPIC HOCKEY" if "olympic" in sport else sport.split('_')[-1].upper(),
                                                "game": f"{game['away_team']} vs {game['home_team']}",
                                                "time": g_time.strftime("%m/%d %I:%M %p"),
                                                "profit": profit, "roi": (profit/max_wager)*100,
                                                "s_team": s['team'], "s_price": s['price'], "s_book": s['book'],
                                                "h_team": best_h['team'], "h_price": best_h['price'], "h_book": best_h['book'],
                                                "hedge": h_amt
                                            })
                    except: continue

        # --- DISPLAY RESULTS ---
        if not all_opps:
            st.warning("No lines found within the selected books.")
        else:
            global_top_3 = sorted(all_opps, key=lambda x: x['roi'], reverse=True)[:3]
            brackets = [("Low Hedge ($0-$50)", 0, 50), ("Med Hedge ($51-$150)", 51, 150), ("High Hedge ($151+)", 151, 9999)]
            
            for label, low, high in brackets:
                matches = sorted([o for o in all_opps if low <= o['hedge'] <= high], key=lambda x: x['roi'], reverse=True)[:3]
                if matches:
                    st.subheader(label)
                    for op in matches:
                        is_star = any(op['game'] == t['game'] and op['roi'] == t['roi'] for t in global_top_3)
                        star = "⭐ " if is_star else ""
                        with st.expander(f"{star}{op['sport']} | {op['game']} | +${op['profit']:.2f}"):
                            c1, c2, c3 = st.columns(3)
                            c1.metric("Source", f"{op['s_book']}", f"{op['s_price']:+}")
                            c1.caption(f"Bet ${max_wager} on {op['s_team']}")
                            c2.metric("Hedge", f"{op['h_book']}", f"{op['h_price']:+}")
                            c2.caption(f"Bet ${op['hedge']:.0f} on {op['h_team']}")
                            c3.metric("ROI", f"{op['roi']:.1f}%")
                            c3.write(f"**Time:** {op['time']}")
