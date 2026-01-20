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
    input::-webkit-outer-spin-button, input::-webkit-inner-spin-button { -webkit-appearance: none; margin: 0; }
    </style>
    """, unsafe_allow_html=True)

# --- HEADER AREA ---
st.title("Promo Converter")
quota_placeholder = st.empty()
quota_placeholder.markdown("**Quota:** :green[Not scanned yet]")

# --- INPUT AREA ---
with st.container():
    with st.form("input_panel"):
        col1, col2, col_hedge = st.columns(3)
        with col1:
            promo_type = st.radio("Strategy", ["Profit Boost (%)", "Bonus Bet", "No-Sweat Bet"], horizontal=True)
        with col2:
            # Standardizing display names
            source_book_display = st.radio("Source Book (Promo)", ["DraftKings", "FanDuel", "BetMGM"], horizontal=True)
            # Internal key mapping
            source_book = source_book_display.lower().replace(" ", "") 
        with col_hedge:
            hedge_book_display = st.radio("Hedge Book (Filter)", ["All Books", "DraftKings", "FanDuel", "BetMGM"], horizontal=True)
            hedge_filter = hedge_book_display.lower().replace(" ", "")

        st.divider()
        col3, col4 = st.columns([3, 1])
        with col3:
            sport_cat = st.radio("Sport", ["All Sports", "NBA", "NFL", "NHL", "NCAAB", "NCAAF"], horizontal=True)
        with col4:
            max_wager_raw = st.text_input("Wager ($)", value="50.0")

        boost_val_raw = st.text_input("Boost (%)", value="50") if promo_type == "Profit Boost (%)" else "0"
        run_scan = st.form_submit_button("Run Optimizer", use_container_width=True)

# --- SCAN LOGIC ---
if run_scan:
    api_key = st.secrets.get("ODDS_API_KEY", "")
    if not api_key:
        st.error("Missing API Key! Set ODDS_API_KEY in Streamlit Secrets.")
    else:
        try:
            max_wager = float(max_wager_raw)
            boost_val = float(boost_val_raw)
        except:
            max_wager, boost_val = 50.0, 0.0

        sport_map = {
            "All Sports": ["basketball_nba", "americanfootball_nfl", "icehockey_nhl", "basketball_ncaab", "americanfootball_ncaaf"],
            "NBA": ["basketball_nba"], "NFL": ["americanfootball_nfl"], "NHL": ["icehockey_nhl"], "NCAAB": ["basketball_ncaab"], "NCAAF": ["americanfootball_ncaaf"]
        }
        
        # Updated BOOK_LIST with internal API keys
        BOOK_LIST = "draftkings,fanduel,betmgm,bet365,williamhill_us,caesars,fanatics,espnbet"
        all_opps = []
        now_utc = datetime.now(timezone.utc)

        with st.spinner(f"Fetching {sport_cat} odds..."):
            sports_to_scan = sport_map.get(sport_cat, [])
            for sport in sports_to_scan:
                # API uses 'us' region for MGM/DraftKings/FanDuel
                url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
                params = {'apiKey': api_key, 'regions': 'us', 'markets': 'h2h', 'bookmakers': BOOK_LIST, 'oddsFormat': 'american'}
                
                try:
                    res = requests.get(url, params=params)
                    quota_rem = res.headers.get('x-requests-remaining', 'N/A')
                    quota_placeholder.markdown(f"**Quota Remaining:** :green[{quota_rem}]")

                    if res.status_code == 200:
                        games = res.json()
                        for game in games:
                            # Filter out games that already started
                            commence_time = datetime.fromisoformat(game['commence_time'].replace('Z', '+00:00'))
                            if commence_time <= now_utc: continue 
                            
                            source_odds = []
                            hedge_odds = []
                            
                            for book in game['bookmakers']:
                                for market in book['markets']:
                                    for o in market['outcomes']:
                                        entry = {'book': book['title'], 'key': book['key'], 'team': o['name'], 'price': o['price']}
                                        
                                        # logic to separate source book and hedge book
                                        if book['key'] == source_book:
                                            source_odds.append(entry)
                                        else:
                                            # Apply the Hedge Filter logic
                                            if hedge_filter == "allbooks" or book['key'] == hedge_filter:
                                                hedge_odds.append(entry)

                            for s in source_odds:
                                # Find opponent team
                                opp_team = [t for t in [game['home_team'], game['away_team']] if t != s['team']][0]
                                eligible_hedges = [h for h in hedge_odds if h['team'] == opp_team]
                                
                                if not eligible_hedges: continue
                                
                                # Pick best price among eligible hedges
                                best_h = max(eligible_hedges, key=lambda x: x['price'])
                                
                                # Convert American to Multiplier
                                s_m = (s['price'] / 100) if s['price'] > 0 else (100 / abs(s['price']))
                                h_m = (best_h['price'] / 100) if best_h['price'] > 0 else (100 / abs(best_h['price']))

                                if promo_type == "Profit Boost (%)":
                                    boosted_s_m = s_m * (1 + (boost_val / 100))
                                    h_needed = round((max_wager * (1 + boosted_s_m)) / (1 + h_m))
                                    profit = min(((max_wager * boosted_s_m) - h_needed), ((h_needed * h_m) - max_wager))
                                    rating = profit
                                elif promo_type == "Bonus Bet":
                                    h_needed = round((max_wager * s_m) / (1 + h_m))
                                    profit = min(((max_wager * s_m) - h_needed), (h_needed * h_m))
                                    rating = (profit / max_wager) * 100
                                else: # No-Sweat
                                    mc = 0.70
                                    h_needed = round((max_wager * (s_m + (1 - mc))) / (h_m + 1))
                                    profit = min(((max_wager * s_m) - h_needed), ((h_needed * h_m) + (max_wager * mc) - max_wager))
                                    rating = (profit / max_wager) * 100

                                # Only add if it's actually an opportunity
                                if profit > -5.0: # Show everything near-profitable for debugging
                                    all_opps.append({
                                        "game": f"{game['away_team']} vs {game['home_team']}",
                                        "sport": sport.split('_')[-1].upper(),
                                        "time": (commence_time - timedelta(hours=6)).strftime("%m/%d %I:%M %p"),
                                        "profit": profit, "hedge": h_needed, "rating": rating,
                                        "s_team": s['team'], "s_book": s['book'], "s_price": s['price'],
                                        "h_team": best_h['team'], "h_book": best_h['book'], "h_price": best_h['price']
                                    })
                except Exception as e:
                    st.error(f"Error on {sport}: {e}")

        # --- RESULTS AREA (REVERTED TO ORIGINAL) ---
        st.write("### Top Scanned Opportunities")
        sorted_opps = sorted(all_opps, key=lambda x: x['rating'], reverse=True)
        if not sorted_opps:
            st.warning(f"No high-value matches found.")
        else:
            for i, op in enumerate(sorted_opps[:10]):
                sport_label = op['sport'].split('_')[-1].upper()
                roi = op['rating'] if promo_type != "Profit Boost (%)" else (op['profit'] / max_wager) * 100
                title = f"RANK {i+1} | {sport_label} | {op['time']} | +${op['profit']:.2f} ({roi:.1f}%)"
                with st.expander(title):
                    st.write(f"**{op['game']}**")
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        st.caption(f"SOURCE: {op['s_book'].upper()}")
                        st.info(f"Bet **${max_wager:.0f}** on {op['s_team']} @ **{op['s_price']:+}**")
                    with c2:
                        st.caption(f"HEDGE: {op['h_book'].upper()}")
                        st.success(f"Bet **${op['hedge']:.0f}** on {op['h_team']} @ **{op['h_price']:+}**")
                    with c3:
                        st.metric("Net Profit", f"${op['profit']:.2f}")
                        st.caption(f"Strategy: {promo_type}")

# --- MANUAL CALCULATOR ---
st.write("---")
st.subheader("Manual Calculator")
with st.expander("Open Manual Calculator", expanded=True):
    with st.form("manual_calc_form"):
        m_promo = st.radio("Strategy", ["Profit Boost (%)", "Bonus Bet", "No-Sweat Bet"], horizontal=True, key="m_strat")
        m_col1, m_col2 = st.columns(2)
        with m_col1:
            m_s_price = st.text_input("Source Odds", value="250")
            m_wager = st.text_input("Wager ($)", value="50.0")
            m_boost = st.text_input("Boost %", value="50") if m_promo == "Profit Boost (%)" else "0"
        with m_col2:
            m_h_price = st.text_input("Hedge Odds", value="-280")
            m_conv = st.text_input("Refund %", value="65") if m_promo == "No-Sweat Bet" else "0"
        
        if st.form_submit_button("Calculate Hedge", use_container_width=True):
            try:
                ms_p, mw, mh_p = float(m_s_price), float(m_wager), float(m_h_price)
                ms_m = (ms_p / 100) if ms_p > 0 else (100 / abs(ms_p))
                mh_m = (mh_p / 100) if mh_p > 0 else (100 / abs(mh_p))
                
                if m_promo == "Profit Boost (%)":
                    boosted_m = ms_m * (1 + float(m_boost)/100)
                    m_h = round((mw * (1 + boosted_m)) / (1 + mh_m))
                    m_p = min(((mw * boosted_m) - m_h), ((m_h * mh_m) - mw))
                elif m_promo == "Bonus Bet":
                    m_h = round((mw * ms_m) / (1 + mh_m))
                    m_p = min(((mw * ms_m) - m_h), (m_h * mh_m))
                else: 
                    mc = float(m_conv)/100 
                    m_h = round((mw * (ms_m + (1 - mc))) / (mh_m + 1))
                    m_p = min(((mw * ms_m) - m_h), ((m_h * mh_m) + (mw * mc) - mw))
                
                st.divider()
                rc1, rc2, rc3 = st.columns(3)
                rc1.metric("Hedge Amount", f"${m_h:.0f}")
                rc2.metric("Net Profit", f"${m_p:.2f}")
                rc3.metric("ROI", f"{((m_p/mw)*100):.1f}%")
            except: 
                st.error("Please enter valid numbers.")





