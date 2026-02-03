import streamlit as st
import requests
from datetime import datetime, timezone, timedelta

# --- PAGE CONFIG ---
st.set_page_config(page_title="Arb Terminal Debug", layout="wide")

# --- INPUT AREA ---
st.title("Promo Converter (theScore Bet Integration)")

with st.sidebar:
    st.header("Settings")
    api_key = st.text_input("Odds API Key", value=st.secrets.get("ODDS_API_KEY", ""), type="password")
    
    # EXACT API KEYS: 'thescore' is the internal key for theScore Bet
    BOOK_MAP = {
        "DraftKings": "draftkings",
        "FanDuel": "fanduel",
        "BetMGM": "betmgm",
        "theScore Bet": "thescore"
    }
    
    source_display = st.selectbox("Source Book", list(BOOK_MAP.keys()))
    source_book = BOOK_MAP[source_display]
    
    promo_type = st.radio("Strategy", ["Profit Boost (%)", "Bonus Bet", "No-Sweat Bet"])
    sport_cat = st.selectbox("Sport", ["NBA", "NHL", "NFL", "NCAAB", "All Sports"])
    max_wager = st.number_input("Wager ($)", value=50.0)
    boost_val = st.number_input("Boost (%)", value=50.0) if promo_type == "Profit Boost (%)" else 0.0

run_scan = st.button("Run Diagnostic Scan", use_container_width=True)

if run_scan:
    if not api_key:
        st.error("Enter an API Key")
    else:
        # Define sports
        sport_map = {"NBA": ["basketball_nba"], "NHL": ["icehockey_nhl"], "NFL": ["americanfootball_nfl"], "NCAAB": ["basketball_ncaab"]}
        sports_to_scan = [key for sublist in sport_map.values() for key in sublist] if sport_cat == "All Sports" else sport_map.get(sport_cat, [])
        
        # We include 'thescore' and 'espnbet' just in case of regional naming overlaps
        BOOK_LIST = "draftkings,fanduel,betmgm,bet365,thescore,espnbet"
        all_opps = []
        found_books = set() # For debugging

        with st.spinner("Fetching Data..."):
            for sport in sports_to_scan:
                url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
                params = {'apiKey': api_key, 'regions': 'us', 'markets': 'h2h', 'bookmakers': BOOK_LIST, 'oddsFormat': 'american'}
                
                res = requests.get(url, params=params)
                if res.status_code == 200:
                    data = res.json()
                    
                    for game in data:
                        source_odds = []
                        hedge_odds = []
                        
                        for book in game['bookmakers']:
                            found_books.add(book['key']) # Track what the API is actually giving us
                            
                            for market in book['markets']:
                                for o in market['outcomes']:
                                    entry = {'book': book['title'], 'key': book['key'], 'team': o['name'], 'price': o['price']}
                                    # Match against our selected key
                                    if book['key'] == source_book:
                                        source_odds.append(entry)
                                    else:
                                        hedge_odds.append(entry)
                        
                        # Calculation Logic
                        for s in source_odds:
                            opp_team = [t for t in [game['home_team'], game['away_team']] if t != s['team']]
                            if not opp_team: continue
                            
                            eligible_hedges = [h for h in hedge_odds if h['team'] == opp_team[0]]
                            if not eligible_hedges: continue
                            
                            best_h = max(eligible_hedges, key=lambda x: x['price'])
                            
                            # Simple conversion for profit check
                            s_m = (s['price']/100) if s['price'] > 0 else (100/abs(s['price']))
                            h_m = (best_h['price']/100) if best_h['price'] > 0 else (100/abs(best_h['price']))
                            
                            # Check for any result (even non-profitable) to see if it's working
                            all_opps.append({
                                "game": f"{game['away_team']} @ {game['home_team']}",
                                "s_book": s['book'],
                                "s_price": s['price'],
                                "h_book": best_h['book'],
                                "h_price": best_h['price']
                            })

        # --- DEBUG CONSOLE ---
        st.divider()
        st.subheader("Diagnostic Results")
        col_a, col_b = st.columns(2)
        
        with col_a:
            st.write("**Books actually found in your region:**")
            st.write(list(found_books))
            if source_book not in found_books:
                st.error(f"❌ '{source_display}' ({source_book}) was NOT found in the API response for this sport.")
            else:
                st.success(f"✅ '{source_display}' was found! If no table appears, no math matches were possible.")

        with col_b:
            st.write(f"**Total Raw Matches Found:** {len(all_opps)}")

        if all_opps:
            st.table(all_opps[:10]) # Show the first 10 matches raw
