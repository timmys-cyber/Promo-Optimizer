# --- SCAN LOGIC (Updated Results Processing) ---
if run_scan:
    # ... [Keep your existing API request and data collection logic here] ...

    if not all_opps:
        st.warning("No matches found. Try changing the Source Book or Strategy.")
    else:
        # 1. Identify "Stars" (Top ROI for each bracket)
        brackets = [
            ("Low Hedge ($0 - $50)", 0, 50), 
            ("Medium Hedge ($51 - $150)", 51, 150), 
            ("High Hedge ($151 - $250)", 151, 250), 
            ("Ultra Hedge ($250+)", 251, 999999)
        ]
        
        # Dictionary to store the best match per bracket
        bracket_stars = {}
        for label, low, high in brackets:
            matches = [o for o in all_opps if low <= o['hedge'] <= high]
            if matches:
                bracket_stars[label] = max(matches, key=lambda x: x['roi'])

        st.write(f"### Scanned {len(all_opps)} Opportunities")

        for label, low, high in brackets:
            bracket_matches = [o for o in all_opps if low <= o['hedge'] <= high]
            sorted_bracket = sorted(bracket_matches, key=lambda x: x['roi'], reverse=True)
            
            if sorted_bracket:
                st.subheader(label)
                for op in sorted_bracket:
                    # 2. Determine if this is the starred result
                    is_star = bracket_stars.get(label) == op
                    star_prefix = "⭐ " if is_star else ""
                    
                    # 3. Define color for the Hedge Amount
                    if op['hedge'] <= 50:
                        hedge_color = "green"
                    elif op['hedge'] <= 150:
                        hedge_color = "orange" # Streamlit uses orange for yellow-ish look
                    else:
                        hedge_color = "red"

                    # title includes Profit as requested
                    title = f"{star_prefix}+${op['profit']:.2f} PROFIT | {op['sport']} | {op['time']}"
                    
                    with st.expander(title):
                        c1, c2, c3 = st.columns(3)
                        with c1:
                            st.caption(f"SOURCE: {op['s_book'].upper()}")
                            st.info(f"Bet **${max_wager:.0f}** on {op['s_team']} @ **{op['s_price']:+}**")
                        with c2:
                            st.caption(f"HEDGE: {op['h_book'].upper()}")
                            # 4. Color code the Hedge Amount text
                            st.markdown(f"Bet :{hedge_color}[**${op['hedge']:.0f}**] on {op['h_team']} @ **{op['h_price']:+}**")
                        with c3:
                            st.metric("Net Profit", f"${op['profit']:.2f}")
                            st.metric("ROI %", f"{op['roi']:.1f}%")
