import streamlit as st
import requests
from datetime import datetime, timezone, timedelta

# --- PAGE CONFIG ---
st.set_page_config(page_title="Arb Terminal", layout="wide")

# --- LIGHT TECH THEME ---
st.markdown("""
    <style>
    .stApp { background-color: #f8f9fb; color: #1e1e1e; }
    div[data-testid="stExpander"] {
        background-color: #ffffff; border: 1px solid #d1d5db;
        border-radius: 12px; margin-bottom: 12px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    [data-testid="stMetricValue"] { 
        color: #008f51 !important; font-family: 'Courier New', monospace; font-weight: 800;
    }
    .stButton>button {
        background-color: #1e1e1e; color: #00ff88; border: none; border-radius: 8px; font-weight: bold;
    }
    </style>
    """, unsafe_allow_html=True)

# --- HEADER AREA ---
st.title("Promo Converter")
quota_placeholder = st.empty()

# --- INPUT AREA ---
with st.container():
    with st.form("input_panel"):
        col1, col2, col_hedge = st.columns(3)
        with col1:
            promo_type = st.radio("Strategy", ["Profit Boost (%)", "Bonus Bet", "No-Sweat Bet"], horizontal=True)
        
        # Mapping Dictionary to fix the "No Results" issue
        BOOK_MAP = {
            "DraftKings": "draftkings",
            "FanDuel": "fanduel",
            "BetMGM": "betmgm",
            "theScore Bet": "thescore"
        }

        with col2:
            source_book_display = st.radio("Source Book", list(BOOK_MAP.keys()), horizontal=True)
            source_book = BOOK_MAP[source_book_display]
        
        with col_hedge:
            hedge_options = ["All Books"] + list(BOOK_MAP.keys())
            hedge_book_display = st.radio("Hedge Filter", hedge_options, horizontal=True)
            hedge_filter = "allbooks" if hedge_book_display == "All Books" else BOOK_MAP[hedge_book_display]

        st.divider()
        sport_labels = ["All Sports", "NBA", "NHL", "NFL", "NCAAB", "ATP", "WTA", "AusOpen(M)", "AusOpen(W)"]
        col3, col4 = st.columns([3, 1])
        with col3:
            sport_cat = st.radio("Sport", sport_labels, horizontal=True)
        with col4:
            max_wager_raw = st.text_input("Wager ($)", value="50.0")

        boost_val_raw = st.text_input("Boost (%)", value="50") if promo_type == "Profit Boost (%)" else "0"
        run_scan = st.form_submit_button("Run Optimizer", use_container_width=True)

# --- SCAN LOGIC ---
if run_scan:
    api_key = st.secrets.get("ODDS_API_KEY", "")
    if not api_key:
        st.error("Missing API Key!")
    else:
        try:
            max_wager, boost_val = float(max_wager_raw), float(boost_val_raw)
        except:
            max_wager, boost_val = 50.0, 0.0

        sport_map = {
            "NBA": ["basketball_nba"], "NHL": ["icehockey_nhl"], "NFL": ["americanfootball_nfl"],
            "NCAAB": ["basketball_ncaab"], "ATP": ["tennis_atp"], "WTA": ["tennis_wta"],
            "AusOpen(M)": ["tennis_atp_aus_open_singles"], "AusOpen(W)": ["tennis_wta_aus_open_singles"]
        }
        
        sports_to_scan = [key for sublist in sport_map.values() for key in sublist] if sport_cat == "All Sports" else sport_map.get(sport_cat, [])
        
        # Ensure 'thescore' is in the API request list
        BOOK_LIST = "draftkings,fanduel,betmgm,bet365,williamhill_us,fanatics,espnbet,thescore"
        all_opps, now_utc = [], datetime.now(timezone.utc)

        with st.spinner(f"Scanning {sport_cat}..."):
            for sport in sports_to_scan:
                url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
                params = {'apiKey': api_key, 'regions': 'us', 'markets': 'h2h', 'bookmakers': BOOK_LIST, 'oddsFormat': 'american'}
                try:
                    res = requests.get(url, params=params)
                    quota_placeholder.markdown(f"**Quota Remaining:** :green[{res.headers.get('x-requests-remaining', 'N/A')}]")
                    if res.status_code == 200:
                        for game in res.json():
                            commence_time = datetime.fromisoformat(game['commence_time'].replace('Z', '+00:00'))
                            if commence_time <= now_utc: continue 
                            
                            source_odds, hedge_odds = [], []
                            for book in game['bookmakers']:
                                for market in book['markets']:
                                    for o in market['outcomes']:
                                        entry = {'book': book['title'], 'key': book['key'], 'team': o['name'], 'price': o['price']}
                                        if book['key'] == source_book: 
                                            source_odds.append(entry)
                                        elif hedge_filter == "allbooks" or book['key'] == hedge_filter: 
                                            hedge_odds.append(entry)

                            # Calculate opportunities
                            for s in source_odds:
                                opp_team = [t for t in [game['home_team'], game['away_team']] if t != s['team']]
                                if not opp_team: continue
                                eligible_hedges = [h for h in hedge_odds if h['team'] == opp_team[0]]
                                if not eligible_hedges: continue
                                
                                best_h = max(eligible_hedges, key=lambda x: x['price'])
                                s_m = (s['price'] / 100) if s['price'] > 0 else (100 / abs(s['price']))
                                h_m = (best_h['price'] / 100) if best_h['price'] > 0 else (100 / abs(best_h['price']))

                                if promo_type == "Profit Boost (%)":
                                    boosted_s_m = s_m * (1 + (boost_val / 100))
                                    h_needed = round((max_wager * (1 + boosted_s_m)) / (1 + h_m))
                                    profit = min(((max_wager * boosted_s_m) - h_needed), ((h_needed * h_m) - max_wager))
                                elif promo_type == "Bonus Bet":
                                    h_needed = round((max_wager * s_m) / (1 + h_m))
                                    profit = min(((max_wager * s_m) - h_needed), (h_needed * h_m))
                                else: 
                                    mc = 0.70
                                    h_needed = round((max_wager * (s_m + (1 - mc))) / (h_m + 1))
                                    profit = min(((max_wager * s_m) - h_needed), ((h_needed * h_m) + (max_wager * mc) - max_wager))

                                if profit > -10.0: # Loosened threshold to show more results
                                    roi = (profit / max_wager) * 100
                                    all_opps.append({
                                        "game": f"{game['away_team']} vs {game['home_team']}",
                                        "sport": sport.upper().replace('TENNIS_',''),
                                        "time": (commence_time - timedelta(hours=6)).strftime("%m/%d %I:%M %p"),
                                        "profit": profit, "hedge": h_needed, "roi": roi,
                                        "s_team": s['team'], "s_book": s['book'], "s_price": s['price'],
                                        "h_team": best_h['team'], "h_book": best_h['book'], "h_price": best_h['price']
                                    })
                except Exception as e: st.error(f"Error: {e}")

        if not all_opps:
            st.warning("No profitable matches found for the selected book and sport. Try 'All Sports' or a different Source Book.")
        else:
            # Display results (Top 3 ROI logic remains the same...)
            top_3_roi_values = sorted([o['roi'] for o in all_opps], reverse=True)[:3]
            st.write(f"### Found {len(all_opps)} Opportunities")
            # ... (rest of your display code)
