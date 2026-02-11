import streamlit as st
import requests
from datetime import datetime, timezone, timedelta

# --- PAGE CONFIG ---
st.set_page_config(page_title="Arb Terminal | Hockey Focus", layout="wide")

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
st.title("Promo Optimizer")
st.caption("2026 Winter Olympics: Men's & Women's Hockey Focus")
quota_placeholder = st.empty()

# --- INPUT AREA ---
with st.container():
    with st.form("input_panel"):
        col1, col2, col_hedge = st.columns(3)
        with col1:
            promo_type = st.radio("Strategy", ["Profit Boost (%)", "Bonus Bet", "No-Sweat Bet"], horizontal=True)
        
        BOOK_MAP = {
            "DraftKings": "draftkings",
            "FanDuel": "fanduel",
            "BetMGM": "betmgm",
            "theScore Bet": "espnbet" 
        }

        with col2:
            source_book_display = st.radio("Source Book", list(BOOK_MAP.keys()), horizontal=True)
            source_book = BOOK_MAP[source_book_display]
        
        with col_hedge:
            hedge_options = ["All Books"] + list(BOOK_MAP.keys())
            hedge_book_display = st.radio("Hedge Filter", hedge_options, horizontal=True)
            hedge_filter = "allbooks" if hedge_book_display == "All Books" else BOOK_MAP[hedge_book_display]

        st.divider()
        # Updated Labels
        sport_labels = ["All Sports", "Olympic Hockey", "NBA", "NHL", "NCAAB", "Tennis"]
        col3, col4 = st.columns([3, 1])
        with col3:
            sport_cat = st.radio("Sport", sport_labels, horizontal=True)
        with col4:
            max_wager_raw = st.text_input("Wager ($)", value="50.0")

        boost_val_raw = st.text_input("Boost (%)", value="50") if promo_type == "Profit Boost (%)" else "0"
        run_scan = st.form_submit_button("Run Full Optimizer", use_container_width=True)

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

        now_utc = datetime.now(timezone.utc)
        scan_limit = (now_utc + timedelta(days=5)).strftime('%Y-%m-%dT%H:%M:%SZ')

        # Focusing specifically on Men's and Women's Hockey Keys
        sport_map = {
            "NBA": ["basketball_nba"], 
            "NHL": ["icehockey_nhl"], 
            "NCAAB": ["basketball_ncaab"],
            "Tennis": ["tennis_atp", "tennis_wta"],
            "Olympic Hockey": [
                "icehockey_winter_olympics",         # Men's
                "icehockey_winter_olympics_womens"   # Women's
            ]
        }
        
        if sport_cat == "All Sports":
            sports_to_scan = [key for sublist in sport_map.values() for key in sublist]
        else:
            sports_to_scan = sport_map.get(sport_cat, [])
        
        BOOK_LIST = "draftkings,fanduel,betmgm,bet365,williamhill_us,fanatics,espnbet"
        all_opps = []

        with st.spinner(f"Scanning {sport_cat}..."):
            for sport in sports_to_scan:
                url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
                params = {
                    'apiKey': api_key, 'regions': 'us', 'markets': 'h2h', 
                    'bookmakers': BOOK_LIST, 'oddsFormat': 'american', 'commenceTimeTo': scan_limit
                }
                
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
                                        if book['key'] == source_book: source_odds.append(entry)
                                        elif hedge_filter == "allbooks" or book['key'] == hedge_filter: hedge_odds.append(entry)

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

                                if profit > -15.0:
                                    roi = (profit / max_wager) * 100
                                    all_opps.append({
                                        "game": f"{game['away_team']} vs {game['home_team']}",
                                        "sport": "OLYMPIC HOCKEY" if "olympics" in sport else sport.upper().replace('BASKETBALL_',''),
                                        "time": (commence_time - timedelta(hours=6)).strftime("%m/%d %I:%M %p"),
                                        "profit": profit, "hedge": h_needed, "roi": roi,
                                        "s_team": s['team'], "s_book": s['book'], "s_price": s['price'],
                                        "h_team": best_h['team'], "h_book": best_h['book'], "h_price": best_h['price']
                                    })
                except Exception as e: st.error(f"Error scanning {sport}: {e}")

        if not all_opps:
            st.warning("No matches found. Note: H2H lines for Olympic Hockey are typically posted 48-72 hours before puck drop.")
        else:
            global_top_3 = sorted(all_opps, key=lambda x: x['roi'], reverse=True)[:3]
            st.write(f"### Found {len(all_opps)} Opportunities | ⭐ = Top 3 Overall")

            brackets = [
                ("Low Hedge ($0 - $50)", 0, 50), 
                ("Medium Hedge ($51 - $150)", 51, 150), 
                ("High Hedge ($151+)", 151, 999999)
            ]

            for label, low, high in brackets:
                b_matches = sorted([o for o in all_opps if low <= o['hedge'] <= high], 
                                   key=lambda x: x['roi'], reverse=True)
                display_matches = b_matches[:3]
                
                if display_matches:
                    st.subheader(label)
                    for op in display_matches:
                        is_global_top = any(
                            op['game'] == top['game'] and 
                            op['s_price'] == top['s_price'] and 
                            op['s_book'] == top['s_book'] 
                            for top in global_top_3
                        )
                        star_prefix = "⭐ " if is_global_top else ""
                        h_color = "green" if op['hedge'] <= 50 else "orange" if op['hedge'] <= 150 else "red"
                        title = f"{star_prefix}+${op['profit']:.2f} PROFIT | {op['sport']} | {op['time']}"
                        
                        with st.expander(title):
                            c1, c2, c3 = st.columns(3)
                            with c1:
                                st.caption(f"SOURCE: {op['s_book'].upper()}")
                                st.info(f"Bet **${max_wager:.0f}** on {op['s_team']} @ **{op['s_price']:+}**")
                            with c2:
                                st.caption(f"HEDGE: {op['h_book'].upper()}")
                                st.markdown(f"Hedge Amount: :{h_color}[**${op['hedge']:.0f}**]")
                                st.success(f"Bet on {op['h_team']} @ **{op['h_price']:+}**")
                            with c3:
                                st.metric("Net Profit", f"${op['profit']:.2f}")
                                st.metric("ROI %", f"{op['roi']:.1f}%")
