# Standardized 5-day window
        now_utc = datetime.now(timezone.utc)
        scan_limit = (now_utc + timedelta(days=5)).strftime('%Y-%m-%dT%H:%M:%SZ')

        # UPDATED: Verified 2026 Olympic Keys
        sport_map = {
            "NBA": ["basketball_nba"], 
            "NHL": ["icehockey_nhl"], 
            "NCAAB": ["basketball_ncaab"],
            "Tennis": ["tennis_atp", "tennis_wta"],
            "Olympic Hockey": [
                "icehockey_winter_olympics",         # Men's Tournament
                "icehockey_winter_olympics_womens",  # Women's Tournament
                "icehockey_sweden_allsvenskan"      # Occasionally used as a fallback key
            ]
        }
        
        if sport_cat == "All Sports":
            # Flatten the list
            sports_to_scan = [key for sublist in sport_map.values() for key in sublist]
        else:
            sports_to_scan = sport_map.get(sport_cat, [])
        
        # --- MODIFIED TIME FILTER ---
        # Allow games that started up to 120 minutes ago for 'Live' conversion
        buffer_start = now_utc - timedelta(minutes=120) 

        # ... (rest of your request logic) ...

        if res.status_code == 200:
            for game in res.json():
                commence_time = datetime.fromisoformat(game['commence_time'].replace('Z', '+00:00'))
                
                # UPDATED: If the game started more than 2 hours ago, skip it
                if commence_time < buffer_start: continue
