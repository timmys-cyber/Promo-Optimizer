if not all_opps:
            st.warning("No matches found.")
        else:
            # --- RESULTS DISPLAY WITH BRACKETS & GLOBAL TOP 3 STARS ---
            brackets = [
                ("Low Hedge ($0 - $50)", 0, 50), 
                ("Medium Hedge ($51 - $150)", 51, 150), 
                ("High Hedge ($151+)", 151, 999999)
            ]
            
            # 1. Identify the Top 3 ROI results across the ENTIRE scan (Global Stars)
            # We sort all results by ROI and take the top 3
            global_top_3 = sorted(all_opps, key=lambda x: x['roi'], reverse=True)[:3]
            
            st.write(f"### Scanned {len(all_opps)} Opportunities | ⭐ = Top 3 Overall")

            for label, low, high in brackets:
                # Filter matches for this bracket and sort by ROI
                b_matches = sorted([o for o in all_opps if low <= o['hedge'] <= high], 
                                   key=lambda x: x['roi'], reverse=True)
                
                # LIMIT TO TOP 3 PER BRACKET for display
                display_matches = b_matches[:3]
                
                if display_matches:
                    st.subheader(label)
                    for op in display_matches:
                        # 2. Check if this specific result is in the Global Top 3
                        is_global_top = any(
                            op['game'] == top['game'] and 
                            op['s_price'] == top['s_price'] and 
                            op['s_book'] == top['s_book'] 
                            for top in global_top_3
                        )
                        
                        star_prefix = "⭐ " if is_global_top else ""
                        
                        # Hedge Color Coding
                        h_color = "green" if op['hedge'] <= 50 else "orange" if op['hedge'] <= 150 else "red"
                        
                        # Preview Title with Profit
                        title = f"{star_prefix}+${op['profit']:.2f} PROFIT | {op['sport']} | {op['time']}"
                        
                        with st.expander(title):
                            c1, c2, c3 = st.columns(3)
                            with c1:
                                st.caption(f"SOURCE: {op['s_book'].upper()}")
                                st.info(f"Bet **${max_wager:.0f}** on {op['s_team']} @ **{op['s_price']:+}**")
                            with c2:
                                st.caption(f"HEDGE: {op['h_book'].upper()}")
                                # Display total hedge amount with color coding scale
                                st.markdown(f"Hedge Amount: :{h_color}[**${op['hedge']:.0f}**]")
                                st.success(f"Bet on {op['h_team']} @ **{op['h_price']:+}**")
                            with c3:
                                st.metric("Net Profit", f"${op['profit']:.2f}")
                                st.metric("ROI %", f"{op['roi']:.1f}%")
