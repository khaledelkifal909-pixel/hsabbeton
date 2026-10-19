import os
from datetime import datetime
from urllib.parse import quote
import webbrowser

from kivy.clock import Clock
from kivy.core.clipboard import Clipboard
from kivy.metrics import dp
from kivy.storage.jsonstore import JsonStore
from kivy.uix.scrollview import ScrollView
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDRaisedButton, MDFlatButton, MDIconButton
from kivymd.uix.card import MDCard
from kivymd.uix.dialog import MDDialog
from kivymd.uix.gridlayout import MDGridLayout
from kivymd.uix.label import MDLabel
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.textfield import MDTextField
from kivymd.uix.toolbar import MDTopAppBar

# الكميات لكل 1 م³ (كلشي بالكيلو، الماء باللتر)
MIX = {
    'Dalle B25 - 310 kg':       dict(ciment=310, ramla=770, g1=526, g2=609, eau=164, adj=3.10),
    'Propreté B20 - 210 kg':    dict(ciment=210, ramla=807, g1=405, g2=767, eau=155, adj=1.68),
    'Béton armé B30 - 340 kg':  dict(ciment=340, ramla=754, g1=565, g2=566, eau=170, adj=4.08),
}

PRICE_FIELDS = [
    ('ciment', "Tman lkhnicha (50 kg)"),
    ('ramla',  "Tman ramla (l tonne)"),
    ('g1',     "Tman G1 (l tonne)"),
    ('g2',     "Tman G2 (l tonne)"),
    ('adj',    "Tman Adj (l kg)"),
]

DENSITE = 1.5  # طن/م³ تقريبي للرمل والگراف، باش نحسبو م³ تقريبية


class BetonApp(MDApp):

    # ---------- أدوات صغيرة ----------
    def field(self, hint, text="", numeric=True):
        kw = dict(input_filter="float") if numeric else {}
        return MDTextField(hint_text=hint, text=text, mode="rectangle",
                           multiline=False, **kw)

    def card(self, title):
        c = MDCard(orientation="vertical", padding=dp(14), spacing=dp(10),
                   adaptive_height=True, radius=[dp(16)], elevation=2)
        c.add_widget(MDLabel(text=title, bold=True, adaptive_height=True))
        return c

    @staticmethod
    def num(field, default=None):
        t = field.text.strip().replace(',', '.')
        if not t:
            return default
        return float(t)

    def msg(self, text):
        d = MDDialog(text=text, buttons=[
            MDFlatButton(text="OK", on_release=lambda x: d.dismiss())])
        d.open()

    # ---------- بناء الواجهة ----------
    def build(self):
        self.title = "Hsab Beton"
        self.theme_cls.primary_palette = "Orange"
        self.store = JsonStore(os.path.join(self.user_data_dir, "beton.json"))
        self.theme_cls.theme_style = (
            self.store.get('cfg')['theme'] if self.store.exists('cfg') else "Light")

        self.items = []
        self.last_report = ""

        root = MDBoxLayout(orientation="vertical")
        root.add_widget(MDTopAppBar(
            title="Hsab Beton", elevation=3,
            right_action_items=[["theme-light-dark", lambda x: self.toggle_theme()]]))

        self.scroll = ScrollView()
        content = MDBoxLayout(orientation="vertical", adaptive_height=True,
                              padding=dp(12), spacing=dp(12))

        # 1) العنصر الحالي
        c1 = self.card("3onsor jdid")
        self.nom = self.field("Smiya (mital: Dalle RDC)", numeric=False)
        c1.add_widget(self.nom)

        self.naw3 = list(MIX.keys())[0]
        self.naw3_btn = MDRaisedButton(text=self.naw3, size_hint_x=1)
        self.naw3_btn.bind(on_release=lambda x: self.menu.open())
        c1.add_widget(self.naw3_btn)
        self.menu = MDDropdownMenu(
            caller=self.naw3_btn, width_mult=5,
            items=[{"text": k, "viewclass": "OneLineListItem",
                    "on_release": (lambda k=k: self.select(k))} for k in MIX])

        row = MDBoxLayout(spacing=dp(8), adaptive_height=True)
        self.toul = self.field("Toul (m)")
        self.l3ard = self.field("L3ard (m)")
        self.l3lo = self.field("L3lo (m)")
        for f in (self.toul, self.l3ard, self.l3lo):
            row.add_widget(f)
        c1.add_widget(row)

        row2 = MDBoxLayout(spacing=dp(8), adaptive_height=True)
        self.qty = self.field("3dad", "1")
        self.dya3 = self.field("Dya3 (%)", "5")
        row2.add_widget(self.qty)
        row2.add_widget(self.dya3)
        c1.add_widget(row2)

        c1.add_widget(MDRaisedButton(text="+ ZID L L2A3MAL", size_hint_x=1,
                                     on_release=lambda x: self.add_item()))
        content.add_widget(c1)

        # 2) لائحة العناصر
        c2 = self.card("L3anassir")
        self.items_box = MDBoxLayout(orientation="vertical",
                                     adaptive_height=True, spacing=dp(4))
        c2.add_widget(self.items_box)
        content.add_widget(c2)
        self.refresh_items()

        # 3) الأثمنة
        c3 = self.card("Tmane (ikhtiyari)")
        self.pf = {}
        saved = self.store.get('prices') if self.store.exists('prices') else {}
        for key, hint in PRICE_FIELDS:
            self.pf[key] = self.field(hint, saved.get(key, ""))
            c3.add_widget(self.pf[key])
        content.add_widget(c3)

        # 4) الأزرار
        btns = MDBoxLayout(spacing=dp(10), adaptive_height=True)
        btns.add_widget(MDRaisedButton(text="L7SSAB", size_hint_x=0.65,
                                       on_release=self.l7ssab))
        btns.add_widget(MDFlatButton(text="MSA7 KOLCHI", size_hint_x=0.35,
                                     on_release=self.msa7))
        content.add_widget(btns)

        # 5) النتيجة
        self.res_card = self.card("Natija")
        self.res_info = MDLabel(text="____", adaptive_height=True)
        self.res_card.add_widget(self.res_info)
        self.res_grid = MDGridLayout(cols=3, adaptive_height=True, spacing=dp(6))
        self.res_card.add_widget(self.res_grid)
        content.add_widget(self.res_card)

        # 6) الرابور
        c6 = self.card("Rapor")
        rb = MDBoxLayout(spacing=dp(6), adaptive_height=True)
        rb.add_widget(MDRaisedButton(text="NSKH", on_release=self.copy_report))
        rb.add_widget(MDRaisedButton(text="WHATSAPP", on_release=self.share_report))
        rb.add_widget(MDRaisedButton(text="7FD", on_release=self.save_report))
        c6.add_widget(rb)
        content.add_widget(c6)

        self.scroll.add_widget(content)
        root.add_widget(self.scroll)
        return root

    # ---------- التفاعل ----------
    def toggle_theme(self):
        new = "Dark" if self.theme_cls.theme_style == "Light" else "Light"
        self.theme_cls.theme_style = new
        self.store.put('cfg', theme=new)

    def select(self, naw3):
        self.naw3 = naw3
        self.naw3_btn.text = naw3
        self.menu.dismiss()

    def add_item(self):
        try:
            t, l, h = self.num(self.toul), self.num(self.l3ard), self.num(self.l3lo)
            if None in (t, l, h):
                raise ValueError
            q = self.num(self.qty, 1)
        except ValueError:
            self.msg("DKHAL AR9AM SHA7 (toul, l3ard, l3lo)")
            return False
        name = self.nom.text.strip() or f"3onsor {len(self.items) + 1}"
        self.items.append(dict(name=name, naw3=self.naw3,
                               toul=t, l3ard=l, l3lo=h, qty=q))
        for f in (self.nom, self.toul, self.l3ard, self.l3lo):
            f.text = ""
        self.qty.text = "1"
        self.refresh_items()
        return True

    def remove_item(self, i):
        if 0 <= i < len(self.items):
            self.items.pop(i)
            self.refresh_items()

    def refresh_items(self):
        self.items_box.clear_widgets()
        if not self.items:
            self.items_box.add_widget(
                MDLabel(text="Mazal ma zdti walo.", adaptive_height=True))
            return
        for i, it in enumerate(self.items):
            v = it['toul'] * it['l3ard'] * it['l3lo'] * it['qty']
            short = it['naw3'].split(' - ')[0]
            row = MDBoxLayout(adaptive_height=True)
            row.add_widget(MDLabel(
                text=(f"{i + 1}. {it['name']} ({short})\n"
                      f"{it['toul']:g}x{it['l3ard']:g}x{it['l3lo']:g}"
                      f" x{it['qty']:g} = {v:.2f} m3"),
                adaptive_height=True))
            row.add_widget(MDIconButton(
                icon="delete", pos_hint={"center_y": .5},
                on_release=lambda x, i=i: self.remove_item(i)))
            self.items_box.add_widget(row)

    def msa7(self, *args):
        self.items = []
        for f in (self.nom, self.toul, self.l3ard, self.l3lo):
            f.text = ""
        self.qty.text = "1"
        self.dya3.text = "5"
        self.refresh_items()
        self.res_info.text = "____"
        self.res_grid.clear_widgets()
        self.last_report = ""

    # ---------- الحساب ----------
    def l7ssab(self, *args):
        # إلا كاين عنصر مكتوب ومازال ما تزادش، نزيدوه بوحدو
        if any(f.text.strip() for f in (self.toul, self.l3ard, self.l3lo)):
            if not self.add_item():
                return
        if not self.items:
            self.msg("Zid 3onsor wa7d 3la l2a9al.")
            return
        try:
            dya3 = self.num(self.dya3, 0)
            prices = {k: self.num(f, 0) for k, f in self.pf.items()}
        except ValueError:
            self.msg("DKHAL AR9AM SHA7 f nisbat dya3 w l2athmina.")
            return

        self.store.put('prices', **{k: self.pf[k].text for k in self.pf})

        tot = dict(ciment=0, ramla=0, g1=0, g2=0, eau=0, adj=0)
        vol_net = 0
        for it in self.items:
            v = it['toul'] * it['l3ard'] * it['l3lo'] * it['qty']
            vol_net += v
            m = MIX[it['naw3']]
            for k in tot:
                tot[k] += v * (1 + dya3 / 100) * m[k]
        vol_tot = vol_net * (1 + dya3 / 100)
        khnaxi = tot['ciment'] / 50

        cost = dict(
            ciment=khnaxi * prices['ciment'],
            ramla=tot['ramla'] / 1000 * prices['ramla'],
            g1=tot['g1'] / 1000 * prices['g1'],
            g2=tot['g2'] / 1000 * prices['g2'],
            adj=tot['adj'] * prices['adj'])
        total = sum(cost.values())
        has_price = any(prices.values())

        def m3(kg):
            return kg / 1000 / DENSITE

        rows = [
            ("Ciment", f"{tot['ciment']:.0f} kg\n({khnaxi:.1f} khnaxi)", cost['ciment']),
            ("Ramla", f"{tot['ramla']:.0f} kg\n(~{m3(tot['ramla']):.1f} m3)", cost['ramla']),
            ("G1", f"{tot['g1']:.0f} kg\n(~{m3(tot['g1']):.1f} m3)", cost['g1']),
            ("G2", f"{tot['g2']:.0f} kg\n(~{m3(tot['g2']):.1f} m3)", cost['g2']),
            ("Eau", f"{tot['eau']:.0f} L", None),
            ("Adj", f"{tot['adj']:.2f} kg", cost['adj']),
        ]

        def price_txt(c):
            return f"{c:.0f}" if (has_price and c is not None) else "-"

        # عرض الجدول
        self.res_info.text = (f"Volume safi : {vol_net:.2f} m3\n"
                              f"Volume m3a dya3 ({dya3:g}%) : {vol_tot:.2f} m3")
        self.res_grid.clear_widgets()
        for head in ("Mada", "Kmiya", "Tmane"):
            self.res_grid.add_widget(MDLabel(text=head, bold=True,
                                             adaptive_height=True))
        for name, qty, c in rows:
            self.res_grid.add_widget(MDLabel(text=name, adaptive_height=True))
            self.res_grid.add_widget(MDLabel(text=qty, adaptive_height=True))
            self.res_grid.add_widget(MDLabel(text=price_txt(c), adaptive_height=True))
        if has_price:
            for txt in ("TOTAL", "", f"{total:.0f}"):
                self.res_grid.add_widget(MDLabel(text=txt, bold=True,
                                                 adaptive_height=True))

        # بناء الرابور
        lines = ["RAPOR - HSAB BETON",
                 datetime.now().strftime("Tarikh: %d/%m/%Y %H:%M"),
                 "-" * 28, "L3anassir:"]
        for i, it in enumerate(self.items, 1):
            v = it['toul'] * it['l3ard'] * it['l3lo'] * it['qty']
            lines.append(f"{i}. {it['name']} ({it['naw3'].split(' - ')[0]}): "
                         f"{it['toul']:g}x{it['l3ard']:g}x{it['l3lo']:g}"
                         f" x{it['qty']:g} = {v:.2f} m3")
        lines += ["-" * 28,
                  f"Volume safi: {vol_net:.2f} m3",
                  f"Volume m3a dya3 ({dya3:g}%): {vol_tot:.2f} m3",
                  "-" * 28]
        for name, qty, c in rows:
            line = f"{name}: {qty.replace(chr(10), ' ')}"
            if has_price and c is not None:
                line += f" = {c:.0f} DH"
            lines.append(line)
        if has_price:
            lines += ["-" * 28, f"TOTAL: {total:.0f} DH"]
        self.last_report = "\n".join(lines)

        Clock.schedule_once(lambda dt: self.scroll.scroll_to(self.res_card), 0.2)

    # ---------- الرابور ----------
    def need_report(self):
        if not self.last_report:
            self.msg("L7ssab lawla bach ykhrej rapor.")
            return False
        return True

    def copy_report(self, *args):
        if self.need_report():
            Clipboard.copy(self.last_report)
            self.msg("Rapor tnsakh. Tqdr tlsqo fin bghiti.")

    def share_report(self, *args):
        if self.need_report():
            webbrowser.open("https://wa.me/?text=" + quote(self.last_report))

    def save_report(self, *args):
        if not self.need_report():
            return
        fname = datetime.now().strftime("rapor_%Y%m%d_%H%M.txt")
        folders = ["/storage/emulated/0/Download", self.user_data_dir]
        for folder in folders:
            try:
                os.makedirs(folder, exist_ok=True)
                path = os.path.join(folder, fname)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(self.last_report)
                self.msg(f"Rapor t7fed f:\n{path}")
                return
            except Exception:
                continue
        self.msg("Ma9drtch n7fed lfile.")


BetonApp().run()
