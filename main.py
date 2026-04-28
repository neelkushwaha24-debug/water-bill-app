import flet as ft
import datetime
import urllib.request
import urllib.parse
import json
import threading
import os
import webbrowser

# वाटर बिल के रेट स्लैब
RATE_SLABS = [
    {"rate": 9.25, "start": datetime.date(1980, 1, 1), "end": datetime.date(1996, 3, 31)},
    {"rate": 40,   "start": datetime.date(1996, 4, 1), "end": datetime.date(2011, 3, 31)},
    {"rate": 80,   "start": datetime.date(2011, 4, 1), "end": datetime.date(2016, 6, 30)},
    {"rate": 100,  "start": datetime.date(2016, 7, 1), "end": datetime.date(2025, 3, 31)},
    {"rate": 150,  "start": datetime.date(2025, 4, 1), "end": datetime.date(2050, 12, 31)}
]

def main(page: ft.Page):
    page.title = "Nagar Palika Water Bill"
    page.theme_mode = ft.ThemeMode.SYSTEM
    # Mobile responsive settings
    page.window.width = 400
    page.window.height = 800
    page.scroll = ft.ScrollMode.AUTO

    STAFF_PIN = "nagar"
    ADMIN_PIN = "master"
    SHEET_URL = "https://script.google.com/macros/s/AKfycbzHh-PCNhDVsTZpVPgBTrK9LkNyXK3aP5XiW_jSkmQiMbSuJWKjHoGEehFXuL0EfZVjQQ/exec"

    state = {
        "lang": "Hindi",
        "global_data": [],
        "filtered_data": [],
        "current_bill_data": None
    }

    # ग्लोबल कैलकुलेटर स्टेट
    calc_state = {
        "wid": "", "old": "", "name": "", "father": "", "ward": "", "address": "",
        "start_date": datetime.date(2011, 1, 1),
        "end_date": datetime.date.today().replace(day=1) - datetime.timedelta(days=1),
        "lok_adalat": False
    }

    def T(hi_text, en_text):
        return hi_text if state["lang"] == "Hindi" else en_text

    # --- Navigation System ---
    def switch_page(e, route):
        page.views.clear()
        if route == "/login":
            page.views.append(build_login_view())
        elif route == "/search":
            page.views.append(build_search_view())
        elif route == "/calc":
            page.views.append(build_calc_view())
        elif route == "/manage":
            page.views.append(build_manage_view())
        elif route == "/settings":
            page.views.append(build_settings_view())
        page.update()

    def build_appbar(title, show_back=True, back_route="/search"):
        leading = ft.IconButton(ft.Icons.ARROW_BACK, on_click=lambda e: switch_page(e, back_route)) if show_back else None
        
        # Mobile specific drawer / menu
        popup_menu = ft.PopupMenuButton(
            items=[
                ft.PopupMenuItem(content=ft.Text(T("🔍 उपभोक्ता सर्च", "🔍 Search")), on_click=lambda e: switch_page(e, "/search")),
                ft.PopupMenuItem(content=ft.Text(T("🧾 कैलकुलेटर", "🧾 Calculator")), on_click=lambda e: switch_page(e, "/calc")),
                ft.PopupMenuItem(content=ft.Text(T("🛡️ डेटा मैनेज", "🛡️ Manage")), on_click=lambda e: verify_admin()),
                ft.PopupMenuItem(content=ft.Text(T("⚙️ सेटिंग्स", "⚙️ Settings")), on_click=lambda e: switch_page(e, "/settings")),
            ]
        )
        return ft.AppBar(
            leading=leading,
            title=ft.Text(title, weight="bold"),
            bgcolor=ft.Colors.SURFACE_CONTAINER,
            actions=[popup_menu]
        )

    # --- Login View ---
    def build_login_view():
        pin_input = ft.TextField(label=T("सीक्रेट पिन डालें", "Enter Secret PIN"), password=True, can_reveal_password=True, text_align=ft.TextAlign.CENTER)
        error_text = ft.Text(color=ft.Colors.RED, visible=False, weight="bold")

        def login_click(e):
            if pin_input.value == STAFF_PIN:
                fetch_data_in_background()
                switch_page(e, "/search")
            else:
                error_text.value = T("❌ गलत पिन!", "❌ Invalid PIN!")
                error_text.visible = True
                page.update()

        return ft.View(
            route="/login",
            vertical_alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Container(
                    padding=30,
                    content=ft.Column([
                        ft.Icon(ft.Icons.WATER_DROP, size=80, color=ft.Colors.BLUE),
                        ft.Text(T("🏢 नगर पालिका परिषद", "🏢 Municipal Council"), size=26, weight="bold", text_align=ft.TextAlign.CENTER),
                        ft.Text(T("सुरक्षित जलकर बिलिंग सिस्टम", "Secure Water Tax Billing System"), text_align=ft.TextAlign.CENTER),
                        ft.Divider(height=40),
                        pin_input,
                        ft.ElevatedButton(T("लॉगिन करें ➔", "Login ➔"), on_click=login_click, width=200, height=50),
                        error_text
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
                )
            ]
        )

    def fetch_data_in_background():
        def task():
            try:
                req = urllib.request.urlopen(SHEET_URL)
                data = json.loads(req.read())
                if data:
                    state["global_data"] = data[1:]
                    state["filtered_data"] = state["global_data"]
                    sb = ft.SnackBar(ft.Text(T(f"✅ {len(state['global_data'])} रिकॉर्ड लोड हो गए!", f"✅ {len(state['global_data'])} records loaded!")), bgcolor=ft.Colors.GREEN)
                    page.overlay.append(sb)
                    sb.open = True
                    # If we are on search page, refresh the list
                    if page.views and page.views[-1].route == "/search":
                        switch_page(None, "/search")
                    else:
                        page.update()
            except Exception as e:
                sb = ft.SnackBar(ft.Text(f"❌ Error: {str(e)}"), bgcolor=ft.Colors.RED)
                page.overlay.append(sb)
                sb.open = True
                page.update()
        threading.Thread(target=task, daemon=True).start()

    # --- Search View ---
    def build_search_view():
        search_wid = ft.TextField(label="Water ID", expand=True, on_change=lambda e: filter_multi())
        search_old = ft.TextField(label="Old ID", expand=True, on_change=lambda e: filter_multi())
        search_name = ft.TextField(label=T("नाम (Name)", "Name"), expand=True, on_change=lambda e: filter_multi())
        search_father = ft.TextField(label=T("पिता (Father)", "Father"), expand=True, on_change=lambda e: filter_multi())
        search_address = ft.TextField(label=T("पता (Address)", "Address"), expand=True, on_change=lambda e: filter_multi())

        search_container = ft.Container(
            padding=10,
            content=ft.Column([
                ft.Row([search_wid, search_old]),
                ft.Row([search_name, search_father]),
                search_address
            ])
        )
        results_list = ft.ListView(expand=True, spacing=10)

        def populate_list(data):
            results_list.controls.clear()
            for row in data[:50]: # Mobile View - 50 items max
                r = list(row) + ["", "", "", "", "", ""]
                wid, old, name, father, ward, address = r[0], r[1], r[2], r[3], r[4], r[5]
                
                def on_select(e, w=wid, o=old, n=name, f=father, wa=ward, a=address):
                    calc_state["wid"] = w; calc_state["old"] = o; calc_state["name"] = n
                    calc_state["father"] = f; calc_state["ward"] = wa; calc_state["address"] = a
                    switch_page(e, "/calc")

                results_list.controls.append(
                    ft.Card(
                        elevation=2,
                        content=ft.ListTile(
                            leading=ft.Icon(ft.Icons.PERSON, color=ft.Colors.BLUE_GREY),
                            title=ft.Text(f"{name} ({father})", weight="bold"),
                            subtitle=ft.Text(f"ID: {wid} | Old ID: {old} | Ward: {ward}\n{address}"),
                            on_click=on_select
                        )
                    )
                )
            page.update()

        def filter_multi():
            q_wid = search_wid.value.lower().strip()
            q_old = search_old.value.lower().strip()
            q_name = search_name.value.lower().strip()
            q_father = search_father.value.lower().strip()
            q_address = search_address.value.lower().strip()
            
            filtered = []
            for row in state["global_data"]:
                r = list(row) + ["", "", "", "", "", ""]
                if (q_wid in str(r[0]).lower() and 
                    q_old in str(r[1]).lower() and 
                    q_name in str(r[2]).lower() and 
                    q_father in str(r[3]).lower() and 
                    q_address in str(r[5]).lower()):
                    filtered.append(row)
            populate_list(filtered)

        if state["filtered_data"]:
            populate_list(state["filtered_data"])
        else:
            results_list.controls.append(ft.Text("Loading data or no records found...", italic=True))

        return ft.View(
            route="/search",
            controls=[
                build_appbar(T("उपभोक्ता सर्च", "Consumer Search"), show_back=False),
                search_container,
                ft.Container(padding=10, expand=True, content=results_list)
            ]
        )

    # --- Calculator View ---
    def build_calc_view():
        name_tf = ft.TextField(label=T("नाम", "Name"), value=calc_state["name"], expand=True)
        father_tf = ft.TextField(label=T("पिता", "Father"), value=calc_state["father"], expand=True)
        ward_tf = ft.TextField(label=T("वार्ड", "Ward"), value=calc_state["ward"], expand=True)
        wid_tf = ft.TextField(label="New ID", value=calc_state["wid"], expand=True)
        addr_tf = ft.TextField(label=T("पता", "Address"), value=calc_state["address"], multiline=True)
        
        def start_date_changed(e):
            if start_dp.value:
                calc_state["start_date"] = start_dp.value.date()
                start_btn.content = calc_state["start_date"].strftime('%d/%m/%Y')
                page.update()

        def end_date_changed(e):
            if end_dp.value:
                calc_state["end_date"] = end_dp.value.date()
                end_btn.content = calc_state["end_date"].strftime('%d/%m/%Y')
                page.update()

        start_dp = ft.DatePicker(on_change=start_date_changed, value=calc_state["start_date"])
        end_dp = ft.DatePicker(on_change=end_date_changed, value=calc_state["end_date"])
        page.overlay.extend([start_dp, end_dp])

        def open_start(e):
            start_dp.open = True
            page.update()

        def open_end(e):
            end_dp.open = True
            page.update()

        start_btn = ft.OutlinedButton(content=calc_state['start_date'].strftime('%d/%m/%Y'), icon=ft.Icons.CALENDAR_MONTH, on_click=open_start, expand=True)
        end_btn = ft.OutlinedButton(content=calc_state['end_date'].strftime('%d/%m/%Y'), icon=ft.Icons.CALENDAR_MONTH, on_click=open_end, expand=True)
        
        adv_tf = ft.TextField(label=T("अग्रिम (₹)", "Advance (₹)"), value="300", keyboard_type=ft.KeyboardType.NUMBER)
        lok_checkbox = ft.Checkbox(label=T("✅ लोक अदालत नियम", "✅ Apply Lok Adalat"), value=calc_state["lok_adalat"])

        result_col = ft.Column(visible=False)

        def calculate_bill(e):
            start_date = calc_state["start_date"]
            end_date = calc_state["end_date"]
            try: adv = float(adv_tf.value or 0)
            except ValueError: adv = 0
            
            if adv > 0 and adv % 150 != 0:
                sb = ft.SnackBar(ft.Text(T("एडवांस 150 के गुणांक में होना चाहिए!", "Advance must be multiple of 150!")), bgcolor=ft.Colors.RED)
                page.overlay.append(sb)
                sb.open = True
                page.update()
                return

            total_bill = 0; last_month_rate = 0; slab_details = []

            def get_overlap(s1, e1, s2, e2):
                start = max(s1, s2); end = min(e1, e2)
                if start > end: return 0
                return (end.year - start.year) * 12 - start.month + end.month + 1

            for slab in RATE_SLABS:
                m = get_overlap(slab["start"], slab["end"], start_date, end_date)
                amount = 0
                if m > 0:
                    amount = m * slab["rate"]; total_bill += amount
                    slab_details.append({"rate": slab["rate"], "start": slab["start"].strftime('%d/%m/%Y'), "end": slab["end"].strftime('%d/%m/%Y'), "m": m, "amt": amount})
                if slab["start"] <= end_date <= slab["end"]: last_month_rate = slab["rate"]

            today = datetime.date.today()
            current_fy_start_year = today.year if today.month >= 4 else today.year - 1
            current_fy_start = datetime.date(current_fy_start_year, 4, 1)
            end_of_arrears = datetime.date(current_fy_start_year, 3, 31)

            arrears_bill = sum(get_overlap(s["start"], s["end"], start_date, min(end_date, end_of_arrears)) * s["rate"] for s in RATE_SLABS)
            current_fy_bill = sum(get_overlap(s["start"], s["end"], max(start_date, current_fy_start), end_date) * s["rate"] for s in RATE_SLABS)

            grace_month = end_date.month + 1; grace_year = end_date.year
            if grace_month > 12: grace_month = 1; grace_year += 1
            grace_due_date = datetime.date(grace_year, grace_month, 15)
            
            is_grace = today <= grace_due_date
            penaltyable_arrears = arrears_bill; penaltyable_cfy = current_fy_bill

            if is_grace and total_bill > 0:
                if current_fy_bill >= last_month_rate: penaltyable_cfy -= last_month_rate
                elif arrears_bill >= last_month_rate: penaltyable_arrears -= last_month_rate

            std_arr_penalty = penaltyable_arrears * 0.10; cfy_penalty = penaltyable_cfy * 0.10
            final_arr_penalty = std_arr_penalty; discount_amt = 0

            lbl_text = T("पेनल्टी 10%", "Penalty 10%")
            if is_grace: lbl_text += f" ({grace_due_date.strftime('%d/%m/%Y')})"

            if lok_checkbox.value:
                if total_bill <= 10000: final_arr_penalty = 0; discount_amt = std_arr_penalty; lbl_text += T(" - 100% माफ़", " (100% Waived)")
                elif total_bill <= 50000: final_arr_penalty = std_arr_penalty * 0.25; discount_amt = std_arr_penalty * 0.75; lbl_text += T(" - 75% माफ़", " (75% Waived)")
                else: final_arr_penalty = std_arr_penalty * 0.50; discount_amt = std_arr_penalty * 0.50; lbl_text += T(" - 50% माफ़", " (50% Waived)")

            final_penalty = final_arr_penalty + cfy_penalty
            total_charge = total_bill + final_penalty + adv

            # Build Result UI Component
            result_col.controls.clear()
            
            for s in slab_details:
                result_col.controls.append(ft.Text(f"₹{s['rate']} ({s['start']}-{s['end']}) | {s['m']} {T('माह', 'm')} = ₹{s['amt']}", size=12))
            
            result_col.controls.append(ft.Divider())
            result_col.controls.append(ft.Row([ft.Text(T("कुल जलकर:", "Bill Amount:"), weight="bold"), ft.Text(f"₹{total_bill:.2f}")], alignment=ft.MainAxisAlignment.SPACE_BETWEEN))
            result_col.controls.append(ft.Row([ft.Text(lbl_text, weight="bold", color=ft.Colors.RED, size=13), ft.Text(f"₹{final_penalty:.2f}", color=ft.Colors.RED)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN))
            if discount_amt > 0:
                result_col.controls.append(ft.Row([ft.Text(T("छूट:", "Discount:"), weight="bold", color=ft.Colors.GREEN), ft.Text(f"- ₹{discount_amt:.2f}", color=ft.Colors.GREEN)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN))
            result_col.controls.append(ft.Row([ft.Text(T("अग्रिम:", "Advance:"), weight="bold", color=ft.Colors.BLUE), ft.Text(f"₹{adv:.2f}", color=ft.Colors.BLUE)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN))
            result_col.controls.append(ft.Divider(color=ft.Colors.ON_SURFACE))
            result_col.controls.append(ft.Row([ft.Text(T("कुल देय राशि:", "Total Payable:"), weight="bold", size=20), ft.Text(f"₹{total_charge:.2f}", weight="bold", size=20)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN))
            
            rmk = T(f"देय राशि ₹{total_charge:.2f} ({start_date.strftime('%d/%m/%y')} - {end_date.strftime('%d/%m/%y')})", f"Total ₹{total_charge:.2f} ({start_date.strftime('%d/%m/%y')} - {end_date.strftime('%d/%m/%y')})")
            if discount_amt > 0: rmk += f"\n(Discount ₹{discount_amt:.2f})"
            
            result_col.controls.append(ft.Text(rmk, color=ft.Colors.ON_SURFACE_VARIANT, italic=True, size=12))
            result_col.visible = True
            
            state["current_bill_data"] = {
                "name": name_tf.value, "father": father_tf.value, "ward": ward_tf.value, "new_id": wid_tf.value,
                "old_id": calc_state["old"], "addr": addr_tf.value, "s_date": start_date.strftime('%d/%m/%Y'),
                "e_date": end_date.strftime('%d/%m/%Y'), "slabs": slab_details, "bill": total_bill,
                "pen": final_penalty, "dis": discount_amt, "adv": adv, "total": total_charge,
                "pen_label": lbl_text, "remark": rmk
            }
            page.update()

        def print_bill(e):
            d = state.get("current_bill_data")
            if not d:
                sb = ft.SnackBar(ft.Text(T("पहले बिल कैलकुलेट करें!", "Calculate Bill First!")), bgcolor=ft.Colors.RED)
                page.overlay.append(sb)
                sb.open = True
                page.update()
                return

            consumer_html = ""
            if d['name'] or d['new_id']:
                consumer_html = f"""
                <div class="info-box">
                    <div style="width: 50%;"><p>{T("नाम:", "Name:")} <span style="color:blue;">{d['name']}</span></p><p>{T("पिता/पति:", "Father/Husband:")} <span style="color:blue;">{d['father']}</span></p><p>{T("पता:", "Address:")} <span style="color:blue;">{d['addr']}</span></p></div>
                    <div style="width: 50%; text-align: right;"><p>{T("न्यू वाटर ID:", "New Water ID:")} <span style="color:blue;">{d['new_id']}</span></p><p>{T("ओल्ड वाटर ID:", "Old Water ID:")} <span style="color:blue;">{d['old_id']}</span></p><p>{T("वार्ड क्र.:", "Ward No.:")} <span style="color:blue;">{d['ward']}</span></p></div>
                </div>
                """

            html_content = f"""
            <!DOCTYPE html><html lang="hi"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>{T("वाटर बिल", "Water Bill")}</title>
                <style>
                    body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; padding: 10px; font-size: 14px; }}
                    .container {{ max-width: 100%; margin: auto; border: 2px solid #333; padding: 10px; border-radius: 8px; }}
                    h2 {{ text-align: center; color: #333; margin-bottom: 15px; border-bottom: 2px solid #333; padding-bottom: 5px; font-size: 18px; }}
                    .info-box {{ display: flex; justify-content: space-between; margin-bottom: 10px; font-weight: bold; font-size: 12px; flex-wrap: wrap; }}
                    table {{ width: 100%; border-collapse: collapse; margin-top: 10px; text-align: center; font-size: 12px; }}
                    th, td {{ border: 1px solid #000; padding: 4px; }}
                    th {{ background-color: #e9ecef !important; }}
                    .bg-bill {{ background-color: #a8e6cf !important; }}
                    .bg-penalty {{ background-color: #ff8b94 !important; color: white !important; }}
                    .bg-discount {{ background-color: #d4edda !important; color: #155724 !important; }}
                    .bg-advance {{ background-color: #4facfe !important; color: white !important; }}
                    .bg-total {{ background-color: #e0e0e0 !important; font-weight: bold; }}
                    .text-right {{ text-align: right; padding-right: 10px; }}
                    .remark {{ margin-top: 15px; padding: 8px; border-left: 5px solid #27ae60; background: #f8f9fa !important; font-weight: bold; font-size: 12px; }}
                </style>
            </head><body onload="window.print()"><div class="container"><h2>{T("वाटर बिल (नगर पालिका परिषद)", "Water Bill (Municipal Council)")}</h2>{consumer_html}
                    <table><thead><tr><th>{T("दर", "Rate")}</th><th>{T("प्रारंभ", "Start")}</th><th>{T("समाप्ति", "End")}</th><th>{T("माह", "M")}</th><th>{T("राशि", "Amount")}</th></tr></thead><tbody>
            """
            for slab in d['slabs']: html_content += f"<tr><td>{slab['rate']}</td><td>{slab['start']}</td><td>{slab['end']}</td><td>{slab['m']}</td><td>{slab['amt']:.2f}</td></tr>"
            html_content += f"""</tbody></table><table style="margin-top: 10px;">
                        <tr><td colspan="4" class="text-right bg-bill">{T("कुल जलकर", "Bill Amount")}</td><td width="25%" class="bg-bill">{d['bill']:.2f}</td></tr>
                        <tr><td colspan="4" class="text-right bg-penalty">{d['pen_label']}</td><td class="bg-penalty">{d['pen']:.2f}</td></tr>
            """
            if d['dis'] > 0: html_content += f"""<tr><td colspan="4" class="text-right bg-discount">{T("लोक अदालत छूट", "Lok Adalat Discount")}</td><td class="bg-discount">- {d['dis']:.2f}</td></tr>"""
            html_content += f"""<tr><td colspan="4" class="text-right bg-advance">{T("अग्रिम", "Advance Payment")}</td><td class="bg-advance">{d['adv']:.2f}</td></tr>
                        <tr><td colspan="4" class="text-right bg-total">{T("कुल देय राशि", "Total Payable")}</td><td class="bg-total">{d['total']:.2f}</td></tr>
                    </table><div class="remark">{d['remark'].replace(chr(10), '<br>')}</div></div></body></html>
            """
            file_path = os.path.abspath("temp_bill_print_mobile.html")
            with open(file_path, "w", encoding="utf-8") as f: f.write(html_content)
            webbrowser.open('file://' + file_path)

        return ft.View(
            route="/calc",
            scroll=ft.ScrollMode.AUTO,
            controls=[
                build_appbar(T("बिल कैलकुलेटर", "Calculator")),
                ft.ExpansionTile(
                    title=ft.Text(T("उपभोक्ता विवरण", "Consumer Details"), weight="bold"),
                    expanded=False,
                    controls=[
                        ft.Row([wid_tf, ward_tf]),
                        ft.Row([name_tf, father_tf]),
                        addr_tf
                    ]
                ),
                ft.Card(
                    elevation=2,
                    content=ft.Container(
                        padding=15,
                        content=ft.Column([
                            ft.Row([ft.Text(T("प्रारंभ:", "Start:")), start_btn], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                            ft.Row([ft.Text(T("समाप्ति:", "End:")), end_btn], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                            adv_tf,
                            lok_checkbox,
                            ft.Row([
                                ft.ElevatedButton(T("कैलकुलेट", "Calculate"), on_click=calculate_bill, bgcolor=ft.Colors.BLUE, color=ft.Colors.WHITE, expand=True),
                                ft.ElevatedButton(T("प्रिंट", "Print"), on_click=print_bill, bgcolor=ft.Colors.GREEN, color=ft.Colors.WHITE, expand=True),
                            ], spacing=10)
                        ])
                    )
                ),
                ft.Card(
                    elevation=2,
                    content=ft.Container(
                        padding=15,
                        content=result_col
                    )
                )
            ]
        )

    def verify_admin():
        def check_pin(e):
            if pin_tf.value == ADMIN_PIN:
                dlg.open = False
                page.update()
                switch_page(e, "/manage")
            else:
                pin_tf.error_text = T("गलत पिन!", "Invalid PIN!")
                page.update()
                
        pin_tf = ft.TextField(label="Admin PIN", password=True)
        dlg = ft.AlertDialog(
            title=ft.Text("Admin Access"),
            content=pin_tf,
            actions=[ft.TextButton("Login", on_click=check_pin)]
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    # --- Manage View ---
    def build_manage_view():
        wid_tf = ft.TextField(label="Water ID")
        old_tf = ft.TextField(label="Old ID")
        name_tf = ft.TextField(label="Name")
        father_tf = ft.TextField(label="Father")
        ward_tf = ft.TextField(label="Ward")
        addr_tf = ft.TextField(label="Address", multiline=True)

        def send_to_server_background(action, wid, old, name, father, ward, address):
            def task():
                try:
                    data = urllib.parse.urlencode({"action": action, "wid": wid, "old": old, "name": name, "father": father, "ward": ward, "address": address}).encode("utf-8")
                    req = urllib.request.Request(SHEET_URL, data=data)
                    urllib.request.urlopen(req)
                except Exception: pass
            threading.Thread(target=task, daemon=True).start()

        search_tf = ft.TextField(label=T("🔍 Water ID खोजें...", "🔍 Search Water ID..."), expand=True)

        def search_record(e):
            q = search_tf.value.strip().lower()
            if not q: return
            for row in state["global_data"]:
                if str(row[0]).lower() == q:
                    wid_tf.value, old_tf.value, name_tf.value, father_tf.value, ward_tf.value, addr_tf.value = [str(x) for x in list(row) + ["","","","","",""]][:6]
                    state["target_wid"] = str(row[0])
                    sb = ft.SnackBar(ft.Text(T("रिकॉर्ड मिल गया!", "Record found!")), bgcolor=ft.Colors.GREEN)
                    page.overlay.append(sb); sb.open = True
                    page.update()
                    return
            sb = ft.SnackBar(ft.Text(T("रिकॉर्ड नहीं मिला!", "Record not found!")), bgcolor=ft.Colors.RED)
            page.overlay.append(sb); sb.open = True
            page.update()

        def update_record(e):
            target = state.get("target_wid", wid_tf.value)
            if not target: return
            for i, row in enumerate(state["global_data"]):
                if str(row[0]) == target:
                    state["global_data"][i] = [wid_tf.value, old_tf.value, name_tf.value, father_tf.value, ward_tf.value, addr_tf.value]
                    send_to_server_background("update", target, old_tf.value, name_tf.value, father_tf.value, ward_tf.value, addr_tf.value)
                    sb = ft.SnackBar(ft.Text(T("रिकॉर्ड अपडेट हो गया!", "Record Updated!")), bgcolor=ft.Colors.GREEN)
                    page.overlay.append(sb); sb.open = True
                    state["target_wid"] = wid_tf.value
                    page.update()
                    return
            sb = ft.SnackBar(ft.Text(T("रिकॉर्ड नहीं मिला!", "Record not found!")), bgcolor=ft.Colors.RED)
            page.overlay.append(sb); sb.open = True
            page.update()

        def delete_record(e):
            target = state.get("target_wid", wid_tf.value)
            if not target: return
            for i, row in enumerate(state["global_data"]):
                if str(row[0]) == target:
                    del state["global_data"][i]
                    send_to_server_background("delete", target, "", "", "", "", "")
                    sb = ft.SnackBar(ft.Text(T("रिकॉर्ड हटा दिया गया!", "Record Deleted!")), bgcolor=ft.Colors.GREEN)
                    page.overlay.append(sb); sb.open = True
                    clear_form(e)
                    return
            sb = ft.SnackBar(ft.Text(T("रिकॉर्ड नहीं मिला!", "Record not found!")), bgcolor=ft.Colors.RED)
            page.overlay.append(sb); sb.open = True
            page.update()

        def add_record(e):
            if not wid_tf.value or not name_tf.value:
                sb = ft.SnackBar(ft.Text(T("Water ID और नाम अनिवार्य है!", "Water ID & Name required!")), bgcolor=ft.Colors.RED)
                page.overlay.append(sb)
                sb.open = True
                page.update()
                return
            new_row = [wid_tf.value, old_tf.value, name_tf.value, father_tf.value, ward_tf.value, addr_tf.value]
            state["global_data"].insert(0, new_row)
            send_to_server_background("add", *new_row)
            sb = ft.SnackBar(ft.Text(T("रिकॉर्ड जुड़ गया!", "Record Added!")), bgcolor=ft.Colors.GREEN)
            page.overlay.append(sb)
            sb.open = True
            clear_form(e)

        def clear_form(e):
            for tf in [search_tf, wid_tf, old_tf, name_tf, father_tf, ward_tf, addr_tf]: tf.value = ""
            state["target_wid"] = ""
            page.update()

        return ft.View(
            route="/manage",
            scroll=ft.ScrollMode.AUTO,
            controls=[
                build_appbar(T("डेटा मैनेज", "Manage Data")),
                ft.Container(
                    padding=20,
                    content=ft.Column([
                        ft.Row([search_tf, ft.IconButton(ft.Icons.SEARCH, on_click=search_record)]),
                        ft.Divider(),
                        ft.Text(T("डेटा फॉर्म", "Data Form"), size=18, weight="bold", color=ft.Colors.ORANGE),
                        wid_tf, old_tf, name_tf, father_tf, ward_tf, addr_tf,
                        ft.Row([
                            ft.ElevatedButton(T("➕ जोड़ें", "➕ Add"), on_click=add_record, bgcolor=ft.Colors.GREEN, color=ft.Colors.WHITE, expand=True),
                            ft.ElevatedButton(T("✏️ अपडेट", "✏️ Update"), on_click=update_record, bgcolor=ft.Colors.BLUE, color=ft.Colors.WHITE, expand=True),
                        ]),
                        ft.Row([
                            ft.ElevatedButton(T("🗑️ डिलीट", "🗑️ Delete"), on_click=delete_record, bgcolor=ft.Colors.RED, color=ft.Colors.WHITE, expand=True),
                            ft.OutlinedButton(T("🧹 साफ़ करें", "🧹 Clear"), on_click=clear_form, expand=True),
                        ])
                    ])
                )
            ]
        )

    # --- Settings View ---
    def build_settings_view():
        def lang_changed(e):
            state["lang"] = lang_dd.value
            switch_page(e, "/settings") 

        def theme_changed(e):
            if theme_dd.value == "Light": page.theme_mode = ft.ThemeMode.LIGHT
            elif theme_dd.value == "Dark": page.theme_mode = ft.ThemeMode.DARK
            else: page.theme_mode = ft.ThemeMode.SYSTEM
            page.update()

        lang_dd = ft.Dropdown(
            label=T("भाषा (Language)", "Language"),
            options=[ft.dropdown.Option("Hindi"), ft.dropdown.Option("English")],
            value=state["lang"],
            on_select=lang_changed
        )
        
        current_theme = "System"
        if page.theme_mode == ft.ThemeMode.LIGHT: current_theme = "Light"
        elif page.theme_mode == ft.ThemeMode.DARK: current_theme = "Dark"

        theme_dd = ft.Dropdown(
            label=T("थीम (Theme)", "Theme"),
            options=[
                ft.dropdown.Option("Light"),
                ft.dropdown.Option("Dark"),
                ft.dropdown.Option("System")
            ],
            value=current_theme,
            on_select=theme_changed
        )

        return ft.View(
            route="/settings",
            controls=[
                build_appbar(T("सेटिंग्स", "Settings")),
                ft.Container(
                    padding=20,
                    content=ft.Column([
                        lang_dd,
                        theme_dd,
                        ft.Divider(),
                        ft.Text("Developed for Mobile with Flet", italic=True, size=12, color=ft.Colors.GREY)
                    ])
                )
            ]
        )

    # Start app
    switch_page(None, "/login")

# Run the app
ft.app(target=main)
