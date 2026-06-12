"""
Option B (production-grade) — Demand Forecast vs Actuals
20-table schema: snowflaked product hierarchy, header/detail orders, SCD2 customers,
multi-currency with FX rates, promotion bridge (M2M), returns, multi-version forecast,
annual plan. Real product/brand/retailer names; all numbers fully synthetic.

Traps for the v1 (undescribed) data agent:
  T1  multi-version forecast -> naive SUM inflates ~6x
  T2  grain mismatch (actuals: line/day/customer/channel; forecast: month/SKU/market)
  T3  forecast horizon extends past last actuals month
  T4  systematic bias by lifecycle (EOL over-, New under-forecast)
  T5  Mar-2026 supply disruption (Power & Charging) absent from forecasts
  T6  viral spike SKU only partially caught by later forecast cycles
  T7  mixed currencies: LocalNetAmount must never be summed across markets
  T8  role-playing dates: OrderDate (active) vs ShipDate/RequestedDeliveryDate (inactive)
  T9  net vs gross: returns must be subtracted for net revenue
  T10 SCD2: counting CustomerKey overcounts accounts (use CustomerId / IsCurrent)
  T11 promo analysis requires the bridge + promo date window
  T12 normalized snowflake: Category lives 2 hops from product
"""
import numpy as np
import pandas as pd
import os

rng = np.random.default_rng(42)
ACT_START, ACT_END, CAL_END = "2024-06-01", "2026-05-31", "2026-11-30"
dates_act = pd.date_range(ACT_START, ACT_END, freq="D")
dates_cal = pd.date_range(ACT_START, CAL_END, freq="D")
Da, Dn = len(dates_act), len(dates_cal)

# ================================================================ dim_date
def fy(d): return d.year + 1 if d.month >= 6 else d.year
def fq(d): return f"FY{fy(d)}-Q{((d.month - 6) % 12)//3 + 1}"
dd = pd.DataFrame({"Date": dates_cal})
dd["DateKey"] = dd.Date.dt.strftime("%Y%m%d").astype(int)
dd["Year"], dd["Quarter"], dd["Month"] = dd.Date.dt.year, dd.Date.dt.quarter, dd.Date.dt.month
dd["MonthName"] = dd.Date.dt.strftime("%B")
dd["MonthKey"] = dd.Date.dt.strftime("%Y%m").astype(int)
dd["Day"], dd["DayOfWeek"] = dd.Date.dt.day, dd.Date.dt.day_name()
dd["IsWeekend"] = dd.Date.dt.dayofweek >= 5
dd["FiscalYear"] = dd.Date.apply(fy); dd["FiscalQuarter"] = dd.Date.apply(fq)
dd["IsFutureMonth"] = dd.Date > pd.Timestamp(ACT_END)
dim_date = dd.copy(); dim_date["Date"] = dim_date.Date.dt.strftime("%Y-%m-%d")

# ================================================================ product snowflake
# (Category, Subcategory, Brand, ProductName, ListPriceUSD)
P = [
 # --- Audio / True Wireless Earbuds
 ("Audio","True Wireless Earbuds","Apple","Apple AirPods Pro 2 (USB-C)",249),
 ("Audio","True Wireless Earbuds","Apple","Apple AirPods 4",129),
 ("Audio","True Wireless Earbuds","Samsung","Samsung Galaxy Buds2 Pro",229),
 ("Audio","True Wireless Earbuds","Samsung","Samsung Galaxy Buds FE",99),
 ("Audio","True Wireless Earbuds","Sony","Sony WF-1000XM5",299),
 ("Audio","True Wireless Earbuds","Sony","Sony LinkBuds S",199),
 ("Audio","True Wireless Earbuds","Anker","Anker Soundcore Liberty 4 NC",99),
 ("Audio","True Wireless Earbuds","Anker","Anker Soundcore P40i",59),
 ("Audio","True Wireless Earbuds","JBL","JBL Tune Flex",99),
 ("Audio","True Wireless Earbuds","JBL","JBL Live Pro 2",149),
 ("Audio","True Wireless Earbuds","Bose","Bose QuietComfort Ultra Earbuds",299),
 ("Audio","True Wireless Earbuds","Jabra","Jabra Elite 8 Active",199),
 # --- Audio / Bluetooth Speakers
 ("Audio","Bluetooth Speakers","JBL","JBL Flip 6",129),
 ("Audio","Bluetooth Speakers","JBL","JBL Charge 5",179),
 ("Audio","Bluetooth Speakers","JBL","JBL Clip 5",79),
 ("Audio","Bluetooth Speakers","Bose","Bose SoundLink Flex",149),
 ("Audio","Bluetooth Speakers","Bose","Bose SoundLink Micro",119),
 ("Audio","Bluetooth Speakers","Sonos","Sonos Roam 2",179),
 ("Audio","Bluetooth Speakers","Sonos","Sonos Move 2",449),
 ("Audio","Bluetooth Speakers","Anker","Anker Soundcore Motion 300",79),
 ("Audio","Bluetooth Speakers","Anker","Anker Soundcore Boom 2",129),
 ("Audio","Bluetooth Speakers","Sony","Sony SRS-XB100",59),
 ("Audio","Bluetooth Speakers","Sony","Sony ULT Field 1",129),
 ("Audio","Bluetooth Speakers","Ultimate Ears","Ultimate Ears Wonderboom 4",99),
 # --- Audio / Soundbars
 ("Audio","Soundbars","Samsung","Samsung HW-Q600C",499),
 ("Audio","Soundbars","Samsung","Samsung HW-B550",279),
 ("Audio","Soundbars","Sonos","Sonos Beam Gen 2",499),
 ("Audio","Soundbars","Sonos","Sonos Ray",279),
 ("Audio","Soundbars","Bose","Bose Smart Soundbar 600",499),
 ("Audio","Soundbars","Bose","Bose TV Speaker",279),
 ("Audio","Soundbars","Sony","Sony HT-S400",299),
 ("Audio","Soundbars","Sony","Sony HT-A3000",499),
 ("Audio","Soundbars","JBL","JBL Bar 5.0 MultiBeam",399),
 ("Audio","Soundbars","JBL","JBL Bar 300",349),
 ("Audio","Soundbars","Vizio","Vizio V-Series V21",179),
 ("Audio","Soundbars","Polk Audio","Polk Audio Signa S4",399),
 # --- Smart Home / Smart Plugs
 ("Smart Home","Smart Plugs","TP-Link","TP-Link Kasa EP25",25),
 ("Smart Home","Smart Plugs","TP-Link","TP-Link Kasa EP10",15),
 ("Smart Home","Smart Plugs","TP-Link","TP-Link Tapo P125M",18),
 ("Smart Home","Smart Plugs","TP-Link","TP-Link Tapo P110",20),
 ("Smart Home","Smart Plugs","Belkin","Belkin Wemo Smart Plug",25),
 ("Smart Home","Smart Plugs","Amazon","Amazon Smart Plug",25),
 ("Smart Home","Smart Plugs","Govee","Govee Smart Plug",15),
 ("Smart Home","Smart Plugs","Meross","Meross Smart Plug Mini",13),
 ("Smart Home","Smart Plugs","Samsung","Samsung SmartThings Outlet",35),
 ("Smart Home","Smart Plugs","Philips Hue","Philips Hue Smart Plug",40),
 ("Smart Home","Smart Plugs","Eve","Eve Energy",40),
 ("Smart Home","Smart Plugs","TP-Link","TP-Link Kasa KP125M",27),
 # --- Smart Home / Security Cameras
 ("Smart Home","Security Cameras","Ring","Ring Indoor Cam (2nd Gen)",60),
 ("Smart Home","Security Cameras","Ring","Ring Stick Up Cam Battery",100),
 ("Smart Home","Security Cameras","Ring","Ring Spotlight Cam Plus",170),
 ("Smart Home","Security Cameras","Arlo","Arlo Pro 5S 2K",250),
 ("Smart Home","Security Cameras","Arlo","Arlo Essential 2K (2nd Gen)",130),
 ("Smart Home","Security Cameras","Wyze","Wyze Cam v4",36),
 ("Smart Home","Security Cameras","Wyze","Wyze Cam Pan v3",40),
 ("Smart Home","Security Cameras","Google Nest","Google Nest Cam (Indoor, Wired)",100),
 ("Smart Home","Security Cameras","Google Nest","Google Nest Cam (Outdoor, Battery)",180),
 ("Smart Home","Security Cameras","TP-Link","TP-Link Tapo C211",35),
 ("Smart Home","Security Cameras","TP-Link","TP-Link Kasa Spot KC410S",45),
 ("Smart Home","Security Cameras","Blink","Blink Mini 2",40),
 # --- Smart Home / Smart Lighting
 ("Smart Home","Smart Lighting","Philips Hue","Philips Hue White & Color A19 Starter Kit",130),
 ("Smart Home","Smart Lighting","Philips Hue","Philips Hue Lightstrip Plus 2m",90),
 ("Smart Home","Smart Lighting","Philips Hue","Philips Hue Go",80),
 ("Smart Home","Smart Lighting","Govee","Govee Glide Wall Light",100),
 ("Smart Home","Smart Lighting","Govee","Govee LED Strip Light M1",60),
 ("Smart Home","Smart Lighting","Govee","Govee Floor Lamp 2",150),
 ("Smart Home","Smart Lighting","LIFX","LIFX Color A19",35),
 ("Smart Home","Smart Lighting","LIFX","LIFX Lightstrip 2m",80),
 ("Smart Home","Smart Lighting","Nanoleaf","Nanoleaf Shapes Hexagons (9-pack)",200),
 ("Smart Home","Smart Lighting","Nanoleaf","Nanoleaf Essentials A19",20),
 ("Smart Home","Smart Lighting","TP-Link","TP-Link Kasa Smart Bulb KL135",13),
 ("Smart Home","Smart Lighting","WiZ","WiZ A19 Color",13),
 # --- Wearables / Fitness Bands
 ("Wearables","Fitness Bands","Fitbit","Fitbit Charge 6",160),
 ("Wearables","Fitness Bands","Fitbit","Fitbit Inspire 3",100),
 ("Wearables","Fitness Bands","Fitbit","Fitbit Luxe",130),
 ("Wearables","Fitness Bands","Xiaomi","Xiaomi Smart Band 9",45),
 ("Wearables","Fitness Bands","Xiaomi","Xiaomi Smart Band 9 Pro",80),
 ("Wearables","Fitness Bands","Garmin","Garmin Vivosmart 5",150),
 ("Wearables","Fitness Bands","Garmin","Garmin Vivofit 4",80),
 ("Wearables","Fitness Bands","Honor","Honor Band 9",40),
 ("Wearables","Fitness Bands","Whoop","Whoop 4.0",239),
 ("Wearables","Fitness Bands","Samsung","Samsung Galaxy Fit3",60),
 ("Wearables","Fitness Bands","Amazfit","Amazfit Band 7",50),
 ("Wearables","Fitness Bands","Garmin","Garmin Vivosmart 4",100),
 # --- Wearables / Smartwatches
 ("Wearables","Smartwatches","Apple","Apple Watch SE (2nd Gen, 40mm)",249),
 ("Wearables","Smartwatches","Apple","Apple Watch Series 9 (41mm)",399),
 ("Wearables","Smartwatches","Samsung","Samsung Galaxy Watch6 (40mm)",299),
 ("Wearables","Smartwatches","Samsung","Samsung Galaxy Watch6 Classic (43mm)",399),
 ("Wearables","Smartwatches","Garmin","Garmin Venu 3",449),
 ("Wearables","Smartwatches","Garmin","Garmin Forerunner 265",449),
 ("Wearables","Smartwatches","Fitbit","Fitbit Versa 4",199),
 ("Wearables","Smartwatches","Fitbit","Fitbit Sense 2",249),
 ("Wearables","Smartwatches","Amazfit","Amazfit GTR 4",199),
 ("Wearables","Smartwatches","Google Nest","Google Pixel Watch 2",349),
 ("Wearables","Smartwatches","Huawei","Huawei Watch GT 4 (46mm)",249),
 ("Wearables","Smartwatches","CMF by Nothing","CMF by Nothing Watch Pro",69),
 # --- Power & Charging / Power Banks
 ("Power & Charging","Power Banks","Anker","Anker PowerCore 10000",26),
 ("Power & Charging","Power Banks","Anker","Anker PowerCore Essential 20000",50),
 ("Power & Charging","Power Banks","Anker","Anker Prime 20K 200W",130),
 ("Power & Charging","Power Banks","Anker","Anker MagGo 10K (Qi2)",90),
 ("Power & Charging","Power Banks","Belkin","Belkin BoostCharge 10K",40),
 ("Power & Charging","Power Banks","Belkin","Belkin BoostCharge Pro 20K",70),
 ("Power & Charging","Power Banks","Ugreen","Ugreen Nexode 20000 145W",80),
 ("Power & Charging","Power Banks","Ugreen","Ugreen 10000 PD 20W",40),
 ("Power & Charging","Power Banks","INIU","INIU Power Bank 10000",24),
 ("Power & Charging","Power Banks","Mophie","Mophie Powerstation XL",60),
 ("Power & Charging","Power Banks","Baseus","Baseus Blade 100W 20000",100),
 ("Power & Charging","Power Banks","Samsung","Samsung 10000 Wireless Battery Pack",80),
 # --- Power & Charging / Wall Chargers
 ("Power & Charging","Wall Chargers","Anker","Anker 735 Nano II 65W",60),
 ("Power & Charging","Wall Chargers","Anker","Anker 511 Nano 30W",23),
 ("Power & Charging","Wall Chargers","Anker","Anker Prime 100W GaN",85),
 ("Power & Charging","Wall Chargers","Belkin","Belkin 65W Dual USB-C",45),
 ("Power & Charging","Wall Chargers","Belkin","Belkin BoostCharge Pro 108W",90),
 ("Power & Charging","Wall Chargers","Ugreen","Ugreen Nexode 65W",56),
 ("Power & Charging","Wall Chargers","Ugreen","Ugreen Nexode 100W",75),
 ("Power & Charging","Wall Chargers","Apple","Apple 20W USB-C Power Adapter",19),
 ("Power & Charging","Wall Chargers","Samsung","Samsung 45W Super Fast Charger",40),
 ("Power & Charging","Wall Chargers","Baseus","Baseus 65W GaN5 Pro",50),
 ("Power & Charging","Wall Chargers","Spigen","Spigen ArcStation Pro 45W",35),
 ("Power & Charging","Wall Chargers","Aukey","Aukey Omnia 100W",70),
]
S = len(P); assert S == 120

cats = sorted({p[0] for p in P})
dim_category = pd.DataFrame({"CategoryKey": range(1, len(cats)+1), "CategoryName": cats})
catkey = dict(zip(dim_category.CategoryName, dim_category.CategoryKey))

subs = sorted({(p[0], p[1]) for p in P})
dim_subcategory = pd.DataFrame([{"SubcategoryKey": i+1, "SubcategoryName": s,
                                 "CategoryKey": catkey[c]} for i, (c, s) in enumerate(subs)])
subkey = {s: k for k, s in zip(dim_subcategory.SubcategoryKey, dim_subcategory.SubcategoryName)}

brand_hq = {"Apple":"United States","Samsung":"South Korea","Sony":"Japan","JBL":"United States",
 "Bose":"United States","Jabra":"Denmark","Sonos":"United States","Anker":"China",
 "Ultimate Ears":"United States","Vizio":"United States","Polk Audio":"United States",
 "TP-Link":"China","Belkin":"United States","Amazon":"United States","Govee":"China",
 "Meross":"China","Philips Hue":"Netherlands","Eve":"Germany","Ring":"United States",
 "Arlo":"United States","Wyze":"United States","Google Nest":"United States","Blink":"United States",
 "LIFX":"Australia","Nanoleaf":"Canada","WiZ":"Netherlands","Fitbit":"United States",
 "Xiaomi":"China","Garmin":"United States","Honor":"China","Whoop":"United States",
 "Amazfit":"China","Huawei":"China","CMF by Nothing":"United Kingdom","Ugreen":"China",
 "INIU":"China","Mophie":"United States","Baseus":"China","Spigen":"South Korea","Aukey":"China"}
brands = sorted({p[2] for p in P})
dim_brand = pd.DataFrame({"BrandKey": range(1, len(brands)+1), "BrandName": brands,
                          "BrandHQCountry": [brand_hq[b] for b in brands]})
brandkey = dict(zip(dim_brand.BrandName, dim_brand.BrandKey))

suppliers = [("SUP-01","Ingram Micro","United States",21,4,0.95),
             ("SUP-02","TD Synnex","United States",24,5,0.93),
             ("SUP-03","D&H Distributing","United States",18,3,0.96),
             ("SUP-04","Westcoast Ltd","United Kingdom",26,6,0.91),
             ("SUP-05","Also Holding","Switzerland",28,6,0.92),
             ("SUP-06","Exertis","Ireland",25,5,0.90),
             ("SUP-07","TD Synnex Japan","Japan",30,7,0.94),
             ("SUP-08","Dicker Data","Australia",32,8,0.89),
             ("SUP-09","Elko Group","Latvia",35,9,0.87),
             ("SUP-10","Intcomex","United States",38,10,0.85)]
dim_supplier = pd.DataFrame(suppliers, columns=["SupplierId","SupplierName","SupplierCountry",
                                                "LeadTimeMeanDays","LeadTimeStdDays","ReliabilityScore"])
dim_supplier.insert(0, "SupplierKey", range(1, 11))

abc_pool = np.array(["A"]*24 + ["B"]*36 + ["C"]*60); rng.shuffle(abc_pool)
life_pool = np.array(["New"]*15 + ["EOL"]*15 + ["Mature"]*90); rng.shuffle(life_pool)
dim_product = pd.DataFrame({
    "ProductKey": range(1, S+1),
    "SKU": [f"SKU-{i+1:04d}" for i in range(S)],
    "ProductName": [p[3] for p in P],
    "SubcategoryKey": [subkey[p[1]] for p in P],
    "BrandKey": [brandkey[p[2]] for p in P],
    "SupplierKey": rng.integers(1, 11, S),
    "ABCClass": abc_pool, "LifecycleStage": life_pool,
    "ListPriceUSD": [float(p[4]) for p in P],
})
dim_product["StandardUnitCostUSD"] = np.round(dim_product.ListPriceUSD * rng.uniform(0.40, 0.58, S), 2)
cat_arr = np.array([p[0] for p in P]); brand_arr = np.array([p[2] for p in P])

new_idx = np.where(life_pool == "New")[0]; eol_idx = np.where(life_pool == "EOL")[0]
launch = np.full(S, np.datetime64(ACT_START)); eolend = np.full(S, np.datetime64(CAL_END))
launch[new_idx] = pd.to_datetime(rng.choice(pd.date_range("2025-01-01","2025-10-01",freq="MS"), len(new_idx))).values
eolend[eol_idx] = pd.to_datetime(rng.choice(pd.date_range("2025-09-01","2026-03-01",freq="MS"), len(eol_idx))).values
dim_product["LaunchDate"] = pd.to_datetime(launch).strftime("%Y-%m-%d")
dim_product["EndOfLifeDate"] = np.where(life_pool == "EOL", pd.to_datetime(eolend).strftime("%Y-%m-%d"), "")

# ================================================================ markets / channels / currency
markets = [("M01","NA-East","North America","United States","USD",1.30),
           ("M02","NA-West","North America","United States","USD",1.10),
           ("M03","LATAM","Latin America","Brazil","BRL",0.55),
           ("M04","EMEA-North","EMEA","Germany","EUR",1.00),
           ("M05","EMEA-South","EMEA","Spain","EUR",0.65),
           ("M06","UK-I","EMEA","United Kingdom","GBP",0.85),
           ("M07","APAC-East","APAC","Japan","JPY",0.90),
           ("M08","APAC-South","APAC","Australia","AUD",0.60)]
dim_market = pd.DataFrame(markets, columns=["MarketId","MarketName","Region","Country","CurrencyCode","_w"])
dim_market.insert(0, "MarketKey", range(1, 9))
mweight = dim_market._w.to_numpy(); dim_market = dim_market.drop(columns="_w")
mkt_ccy = dict(zip(dim_market.MarketId, dim_market.CurrencyCode))

dim_channel = pd.DataFrame({"ChannelKey":[1,2,3],"ChannelId":["CH1","CH2","CH3"],
    "ChannelName":["Retail","eCommerce","Distributor"],"StandardDiscountPct":[0.05,0.10,0.25]})
ch_disc = dict(zip(dim_channel.ChannelId, dim_channel.StandardDiscountPct))

dim_currency = pd.DataFrame({"CurrencyCode":["USD","EUR","GBP","BRL","JPY","AUD"],
    "CurrencyName":["US Dollar","Euro","British Pound","Brazilian Real","Japanese Yen","Australian Dollar"],
    "Symbol":["$","€","£","R$","¥","A$"]})

# FX: units of local currency per 1 USD, daily random walk
fx0 = {"USD":1.0,"EUR":0.92,"GBP":0.79,"BRL":5.40,"JPY":152.0,"AUD":1.52}
fx_rows = []
fx_lookup = {}
for ccy, r0 in fx0.items():
    steps = rng.normal(0, 0.003, Dn); steps[0] = 0
    series = r0 * np.exp(np.cumsum(steps)) if ccy != "USD" else np.ones(Dn)
    fx_lookup[ccy] = series
    fx_rows.append(pd.DataFrame({"DateKey": dim_date.DateKey, "CurrencyCode": ccy,
                                 "RatePerUSD": np.round(series, 6)}))
fact_fx_rate = pd.concat(fx_rows, ignore_index=True)

# ================================================================ customers (SCD2)
# (CustomerId, Name, MarketId, ChannelId, weight, initial segment)
C = [("C001","Best Buy","M01","CH1",3.0,"Strategic"),("C002","Target","M01","CH1",2.2,"Key Account"),
     ("C003","Micro Center","M01","CH1",1.0,"Mid-Market"),("C004","B&H Photo Video","M01","CH1",0.9,"Mid-Market"),
     ("C005","Amazon US","M01","CH2",3.5,"Strategic"),("C006","Ingram Micro NA","M01","CH3",2.0,"Strategic"),
     ("C007","Costco Wholesale","M02","CH1",2.5,"Strategic"),("C008","Walmart","M02","CH1",3.0,"Strategic"),
     ("C009","Staples","M02","CH1",0.8,"Mid-Market"),("C010","Newegg","M02","CH2",1.4,"Key Account"),
     ("C011","TD Synnex US","M02","CH3",1.8,"Key Account"),
     ("C012","Mercado Libre","M03","CH2",2.5,"Strategic"),("C013","Magazine Luiza","M03","CH1",1.8,"Key Account"),
     ("C014","Casas Bahia","M03","CH1",1.4,"Mid-Market"),("C015","Fast Shop","M03","CH1",0.8,"Mid-Market"),
     ("C016","Intcomex LATAM","M03","CH3",1.2,"Mid-Market"),
     ("C017","MediaMarkt","M04","CH1",3.0,"Strategic"),("C018","Saturn","M04","CH1",1.6,"Key Account"),
     ("C019","Otto","M04","CH2",1.4,"Key Account"),("C020","Coolblue","M04","CH2",1.5,"Key Account"),
     ("C021","Amazon DE","M04","CH2",2.6,"Strategic"),("C022","Also Holding DACH","M04","CH3",1.6,"Key Account"),
     ("C023","FNAC","M05","CH1",1.8,"Key Account"),("C024","El Corte Inglés","M05","CH1",1.6,"Key Account"),
     ("C025","Worten","M05","CH1",1.0,"Mid-Market"),("C026","Unieuro","M05","CH1",1.0,"Mid-Market"),
     ("C027","Exertis Iberia","M05","CH3",0.9,"Mid-Market"),
     ("C028","Currys","M06","CH1",2.4,"Strategic"),("C029","Argos","M06","CH1",1.8,"Key Account"),
     ("C030","John Lewis","M06","CH1",1.2,"Key Account"),("C031","AO.com","M06","CH2",1.0,"Mid-Market"),
     ("C032","Amazon UK","M06","CH2",2.2,"Strategic"),("C033","Westcoast UK","M06","CH3",1.4,"Key Account"),
     ("C034","Yodobashi Camera","M07","CH1",2.4,"Strategic"),("C035","Bic Camera","M07","CH1",2.0,"Key Account"),
     ("C036","Yamada Denki","M07","CH1",1.6,"Key Account"),("C037","Rakuten","M07","CH2",1.8,"Key Account"),
     ("C038","TD Synnex Japan","M07","CH3",1.2,"Mid-Market"),
     ("C039","JB Hi-Fi","M08","CH1",2.2,"Strategic"),("C040","Harvey Norman","M08","CH1",1.6,"Key Account"),
     ("C041","Officeworks","M08","CH1",1.0,"Mid-Market"),("C042","The Good Guys","M08","CH1",1.0,"Mid-Market"),
     ("C043","Amazon AU","M08","CH2",1.2,"Key Account"),("C044","Dicker Data","M08","CH3",1.3,"Key Account"),
     ("C045","TechData Reseller Group","M02","CH3",0.6,"Mid-Market")]
cust = pd.DataFrame(C, columns=["CustomerId","CustomerName","MarketId","ChannelId","Weight","Segment"])

# SCD2: 8 accounts get a segment upgrade during 2025
scd_rows, ck = [], 1
upgrades = rng.choice(cust.index[cust.Segment != "Strategic"], 8, replace=False)
upg_dates = pd.to_datetime(rng.choice(pd.date_range("2025-02-01","2025-12-01",freq="MS"), 8))
upg_map = dict(zip(upgrades, upg_dates))
for i, r in cust.iterrows():
    if i in upg_map:
        chg = upg_map[i]
        scd_rows.append([ck, r.CustomerId, r.CustomerName, r.MarketId, r.ChannelId, r.Segment,
                         ACT_START, (chg - pd.Timedelta(days=1)).strftime("%Y-%m-%d"), False]); ck += 1
        new_seg = "Strategic" if r.Segment == "Key Account" else "Key Account"
        scd_rows.append([ck, r.CustomerId, r.CustomerName, r.MarketId, r.ChannelId, new_seg,
                         chg.strftime("%Y-%m-%d"), "9999-12-31", True]); ck += 1
    else:
        scd_rows.append([ck, r.CustomerId, r.CustomerName, r.MarketId, r.ChannelId, r.Segment,
                         ACT_START, "9999-12-31", True]); ck += 1
dim_customer = pd.DataFrame(scd_rows, columns=["CustomerKey","CustomerId","CustomerName","MarketId",
                                               "ChannelId","Segment","ValidFrom","ValidTo","IsCurrent"])

# ================================================================ promotions + bridge
promo_events = [("PR01","Black Friday 2024","Audio",2024,11,1.8),("PR02","Black Friday 2024","Smart Home",2024,11,1.7),
 ("PR03","Black Friday 2024","Wearables",2024,11,1.6),("PR04","Black Friday 2024","Power & Charging",2024,11,1.5),
 ("PR05","Spring Smart Home Sale 2025","Smart Home",2025,4,1.45),("PR06","Summer Travel Promo 2025","Power & Charging",2025,6,1.40),
 ("PR07","Back to School Audio 2025","Audio",2025,7,1.35),
 ("PR08","Black Friday 2025","Audio",2025,11,1.85),("PR09","Black Friday 2025","Smart Home",2025,11,1.75),
 ("PR10","Black Friday 2025","Wearables",2025,11,1.65),("PR11","Black Friday 2025","Power & Charging",2025,11,1.55),
 ("PR12","Spring Fitness Promo 2026","Wearables",2026,4,1.40)]
dim_promotion = pd.DataFrame([{
    "PromotionId": pid, "PromotionName": f"{name} — {cat}",
    "StartDate": f"{y}-{m:02d}-01",
    "EndDate": (pd.Timestamp(y, m, 1) + pd.offsets.MonthEnd(0)).strftime("%Y-%m-%d"),
    "DiscountDepthPct": round((lift - 1) * 0.25, 3), "FundingType": rng.choice(["Vendor-funded","Co-op","Self-funded"]),
} for (pid, name, cat, y, m, lift) in promo_events])

bridge_rows, promo_lift_sku = [], {}
for (pid, name, cat, y, m, lift) in promo_events:
    members = np.where(cat_arr == cat)[0]
    members = rng.choice(members, int(len(members) * 0.7), replace=False)
    for i in members:
        bridge_rows.append({"PromotionId": pid, "SKU": dim_product.SKU.iloc[i]})
    promo_lift_sku[(y * 100 + m)] = promo_lift_sku.get(y * 100 + m, {})
    for i in members:
        promo_lift_sku[y * 100 + m][i] = lift
bridge_promotion_product = pd.DataFrame(bridge_rows)

# ================================================================ demand engine
month_of = dates_cal.month.to_numpy(); ym = dates_cal.year.to_numpy() * 100 + month_of
dow = np.where(dates_cal.dayofweek >= 5, 0.90, 1.04)
seas = {"Audio":[.85,.80,.90,.95,1.0,1.0,.95,1.0,1.05,1.10,1.45,1.60],
        "Smart Home":[.95,.90,.95,1.0,1.05,1.0,.95,.95,1.0,1.10,1.35,1.45],
        "Wearables":[1.40,1.05,.95,.95,1.0,1.0,.90,.90,.95,1.0,1.30,1.50],
        "Power & Charging":[.90,.85,.95,1.0,1.10,1.25,1.30,1.15,1.0,1.0,1.25,1.35]}
base_map = {"A":2.6,"B":0.75,"C":0.13}
base = np.array([base_map[c] for c in abc_pool]) * rng.lognormal(0, 0.35, S)
seas_d = np.stack([np.array(seas[c])[month_of - 1] for c in cat_arr])

life = np.ones((S, Dn)); day_idx = np.arange(Dn)
launch_off = ((pd.to_datetime(dim_product.LaunchDate) - pd.Timestamp(ACT_START)).dt.days).to_numpy()
for i in new_idx:
    ramp = np.clip((day_idx - launch_off[i]) / 120.0, 0, 1)
    life[i] = np.where(day_idx < launch_off[i], 0.0, 0.15 + 0.85 * ramp)
eol_off = np.full(S, 10**9)
eol_dt = pd.to_datetime(pd.Series(np.where(life_pool == "EOL",
         pd.to_datetime(eolend).strftime("%Y-%m-%d"), None)))
for i in eol_idx:
    off = (eol_dt.iloc[i] - pd.Timestamp(ACT_START)).days; eol_off[i] = off
    decay = np.clip(1 - (day_idx - (off - 180)) / 180.0, 0, 1)
    life[i] = np.minimum(life[i], np.where(day_idx >= off, 0.0, decay))

promo_full = np.ones((S, Dn)); promo_known = np.ones((S, Dn))
for mkey, lifts in promo_lift_sku.items():
    dmask = ym == mkey
    for i, lift in lifts.items():
        promo_full[i, dmask] = lift
        promo_known[i, dmask] = 1 + (lift - 1) * 0.6

mean = base[:, None, None] * mweight[None, :, None] * (seas_d * life * promo_full * dow[None, :])[:, None, :]
mean_act = mean.copy()
pc_idx = np.where(cat_arr == "Power & Charging")[0]
mean_act[np.ix_(pc_idx, np.arange(8), np.where(ym == 202603)[0])] *= 0.45
spike_sku = int(np.where((cat_arr == "Wearables") & (life_pool == "Mature") & (abc_pool == "A"))[0][0])
mean_act[spike_sku][:, (ym == 202510) | (ym == 202511)] *= 3.5

# ================================================================ orders (header + lines)
qty = rng.poisson(mean_act[:, :, :Da])
si, ki, di = np.nonzero(qty); n = len(si)
datekeys_act = dim_date.DateKey.to_numpy()[:Da]
lines = pd.DataFrame({"di": di, "DateKey": datekeys_act[di],
                      "SKU": dim_product.SKU.to_numpy()[si], "ProdIdx": si,
                      "MarketId": dim_market.MarketId.to_numpy()[ki], "QtySold": qty[si, ki, di]})
# assign customer within market by weight
cust_by_mkt = {m: cust[cust.MarketId == m] for m in dim_market.MarketId}
cust_assign = np.empty(n, dtype=object)
for m, grp in cust_by_mkt.items():
    mask = (lines.MarketId == m).to_numpy()
    w = grp.Weight.to_numpy(); w = w / w.sum()
    cust_assign[mask] = rng.choice(grp.CustomerId.to_numpy(), mask.sum(), p=w)
lines["CustomerId"] = cust_assign

# order = (date, customer); header attributes
hdr = lines.groupby(["DateKey","di","CustomerId","MarketId"], as_index=False).size()
hdr["OrderId"] = [f"SO-{i:07d}" for i in range(1, len(hdr) + 1)]
ship_lag = rng.integers(1, 8, len(hdr)); req_lag = ship_lag + rng.integers(2, 11, len(hdr))
order_dt = pd.to_datetime(hdr.DateKey.astype(str))
hdr["ShipDateKey"] = (order_dt + pd.to_timedelta(ship_lag, "D")).dt.strftime("%Y%m%d").astype(int)
hdr["RequestedDeliveryDateKey"] = (order_dt + pd.to_timedelta(req_lag, "D")).dt.strftime("%Y%m%d").astype(int)
cmap = cust.set_index("CustomerId")
hdr["ChannelId"] = cmap.loc[hdr.CustomerId, "ChannelId"].to_numpy()
hdr["CurrencyCode"] = hdr.MarketId.map(mkt_ccy)
hdr["ShipMethod"] = rng.choice(["Ground","Air","Sea","Parcel"], len(hdr), p=[.45,.15,.15,.25])
# SCD2 surrogate key valid at order date
dc = dim_customer.copy()
dc["VF"] = pd.to_datetime(dc.ValidFrom); dc["VT"] = pd.to_datetime(dc.ValidTo.replace("9999-12-31","2099-12-31"))
hdr_dt = order_dt.to_numpy()
hdr["CustomerKey"] = 0
for cid, g in dc.groupby("CustomerId"):
    msk = (hdr.CustomerId == cid).to_numpy()
    if len(g) == 1:
        hdr.loc[msk, "CustomerKey"] = g.CustomerKey.iloc[0]
    else:
        g = g.sort_values("VF")
        cut = g.VF.iloc[1]
        hdr.loc[msk & (hdr_dt < np.datetime64(cut)), "CustomerKey"] = g.CustomerKey.iloc[0]
        hdr.loc[msk & (hdr_dt >= np.datetime64(cut)), "CustomerKey"] = g.CustomerKey.iloc[1]
fact_order_header = hdr[["OrderId","DateKey","ShipDateKey","RequestedDeliveryDateKey","CustomerKey",
                         "CustomerId","MarketId","ChannelId","CurrencyCode","ShipMethod"]].rename(
                         columns={"DateKey":"OrderDateKey"})

# lines: pricing in USD + local
lines = lines.merge(hdr[["DateKey","CustomerId","OrderId","ChannelId","CurrencyCode"]],
                    on=["DateKey","CustomerId"], how="left")
lp = dim_product.ListPriceUSD.to_numpy()[lines.ProdIdx]
sc = dim_product.StandardUnitCostUSD.to_numpy()[lines.ProdIdx]
disc = lines.ChannelId.map(ch_disc).to_numpy()
unit_usd = np.round(lp * (1 - disc) * rng.normal(1, 0.02, len(lines)), 2)
rates = np.array([fx_lookup[c][d] for c, d in zip(lines.CurrencyCode, lines.di)])
fact_order_line = pd.DataFrame({
    "SalesOrderLineId": np.arange(1, len(lines) + 1),
    "OrderId": lines.OrderId, "DateKey": lines.DateKey, "SKU": lines.SKU,
    "QtySold": lines.QtySold,
    "UnitPriceUSD": unit_usd, "UnitCostUSD": np.round(sc * rng.normal(1, 0.015, len(lines)), 2),
    "NetAmountUSD": np.round(lines.QtySold * unit_usd, 2),
    "CurrencyCode": lines.CurrencyCode,
    "LocalUnitPrice": np.round(unit_usd * rates, 2),
    "LocalNetAmount": np.round(lines.QtySold * unit_usd * rates, 2),
})

# ================================================================ returns
ret_p = np.where(brand_arr[lines.ProdIdx] == "Govee", 0.09, 0.025)
is_ret = rng.random(len(lines)) < ret_p
ridx = np.where(is_ret)[0]
ret_lag = rng.integers(5, 31, len(ridx))
ret_date = pd.to_datetime(lines.DateKey.iloc[ridx].astype(str)) + pd.to_timedelta(ret_lag, "D")
ret_date = ret_date.clip(upper=pd.Timestamp(CAL_END))
reasons = ["Defective","Damaged in transit","Wrong item shipped","Customer remorse","Warranty claim"]
dim_return_reason = pd.DataFrame({"ReasonKey": range(1, 6), "ReasonName": reasons,
    "IsQualityRelated": [True, False, False, False, True]})
r_reason = np.where(brand_arr[lines.ProdIdx.iloc[ridx]] == "Govee",
                    rng.choice([1,2,3,4,5], len(ridx), p=[.62,.08,.05,.10,.15]),
                    rng.choice([1,2,3,4,5], len(ridx), p=[.25,.15,.15,.30,.15]))
ret_qty = np.minimum(lines.QtySold.iloc[ridx].to_numpy(), rng.integers(1, 3, len(ridx)))
fact_returns = pd.DataFrame({
    "ReturnId": [f"RMA-{i:06d}" for i in range(1, len(ridx) + 1)],
    "ReturnDateKey": ret_date.dt.strftime("%Y%m%d").astype(int),
    "SalesOrderLineId": fact_order_line.SalesOrderLineId.iloc[ridx].to_numpy(),
    "OrderId": lines.OrderId.iloc[ridx].to_numpy(),
    "SKU": lines.SKU.iloc[ridx].to_numpy(),
    "MarketId": lines.MarketId.iloc[ridx].to_numpy(),
    "CustomerId": lines.CustomerId.iloc[ridx].to_numpy(),
    "ReasonKey": r_reason, "QtyReturned": ret_qty,
    "RefundAmountUSD": np.round(ret_qty * unit_usd[ridx], 2),
})

# ================================================================ forecast (multi-version) + plan
life_plan = life.copy()
for i in eol_idx:
    life_plan[i] = np.clip(life[i] + 0.18 * (life[i] > 0) + 0.10 * (day_idx >= eol_off[i] - 180), 0, 1.2)
for i in new_idx:
    life_plan[i] = life[i] * 0.82
mean_plan = base[:, None, None] * mweight[None, :, None] * (seas_d * life_plan * promo_known * dow[None, :])[:, None, :]

months = pd.period_range("2024-06","2026-11",freq="M")
msk_key = {p: int(p.start_time.strftime("%Y%m%d")) for p in months}
mon_idx = {p: np.where(ym == p.year * 100 + p.month)[0] for p in months}
E = {p: mean_plan[:, :, mon_idx[p]].sum(axis=2) for p in months}
blend_price = dim_product.ListPriceUSD.to_numpy() * 0.90
active_any = mean_plan.sum(axis=(1, 2)) > 0

versions, fc_rows = [], []
ver_months = pd.period_range("2024-06","2026-05",freq="M")
for vi, vp in enumerate(ver_months, 1):
    vid = f"FC-{vp.year}-{vp.month:02d}"
    versions.append({"ForecastVersionKey": vi, "VersionId": vid,
                     "VersionName": f"Forecast Cycle {vp.strftime('%B %Y')}",
                     "SnapshotDate": vp.start_time.strftime("%Y-%m-%d"),
                     "IsLatest": vp == ver_months[-1]})
    for lag in range(1, 7):
        tp = vp + lag
        if tp not in msk_key: continue
        adj = E[tp].copy()
        if tp.year * 100 + tp.month in (202510, 202511) and vp >= pd.Period("2025-10","M"):
            adj[spike_sku, :] *= 2.8
        noise = np.clip(rng.normal(1.0, 0.05 + 0.03 * lag, adj.shape), 0.3, 2.0)
        F = np.round(adj * noise).astype(int)
        ssel, ksel = np.nonzero((F > 0) & active_any[:, None])
        if not len(ssel): continue
        fc_rows.append(pd.DataFrame({"VersionId": vid, "DateKey": msk_key[tp],
            "SKU": dim_product.SKU.to_numpy()[ssel], "MarketId": dim_market.MarketId.to_numpy()[ksel],
            "LagMonths": lag, "ForecastQty": F[ssel, ksel],
            "ForecastRevenueUSD": np.round(F[ssel, ksel] * blend_price[ssel], 2)}))
dim_forecast_version = pd.DataFrame(versions)
fact_forecast = pd.concat(fc_rows, ignore_index=True)

plan_rows = []
for fy_, span in [("FY2025", pd.period_range("2024-06","2025-05",freq="M")),
                  ("FY2026", pd.period_range("2025-06","2026-05",freq="M"))]:
    for p in span:
        dfp = pd.DataFrame({"Category": cat_arr.repeat(8),
                            "MarketId": np.tile(dim_market.MarketId.to_numpy(), S),
                            "Qty": E[p].ravel(), "Rev": (E[p] * blend_price[:, None]).ravel()})
        g = dfp.groupby(["Category","MarketId"], as_index=False).sum()
        g["FiscalYear"], g["DateKey"] = fy_, msk_key[p]
        g["PlanQty"] = np.round(g.Qty * 1.05).astype(int)
        g["PlanRevenueUSD"] = np.round(g.Rev * 1.05, 2)
        plan_rows.append(g[["DateKey","FiscalYear","Category","MarketId","PlanQty","PlanRevenueUSD"]])
fact_annual_plan = pd.concat(plan_rows, ignore_index=True)

# ================================================================ save
from pathlib import Path
out = str(Path(__file__).resolve().parent / "data"); os.makedirs(out, exist_ok=True)
tables = {"dim_date": dim_date, "dim_category": dim_category, "dim_subcategory": dim_subcategory,
          "dim_brand": dim_brand, "dim_supplier": dim_supplier, "dim_product": dim_product,
          "dim_market": dim_market, "dim_channel": dim_channel, "dim_currency": dim_currency,
          "dim_customer": dim_customer, "dim_promotion": dim_promotion,
          "bridge_promotion_product": bridge_promotion_product,
          "dim_forecast_version": dim_forecast_version, "dim_return_reason": dim_return_reason,
          "fact_order_header": fact_order_header, "fact_order_line": fact_order_line,
          "fact_returns": fact_returns, "fact_fx_rate": fact_fx_rate,
          "fact_forecast": fact_forecast, "fact_annual_plan": fact_annual_plan}
for name, df in tables.items():
    df.to_csv(f"{out}/{name}.csv", index=False)
    print(f"{name:26s} rows={len(df):>9,}  cols={df.shape[1]}")
print(f"\nSpike SKU: {dim_product.SKU.iloc[spike_sku]} = {dim_product.ProductName.iloc[spike_sku]}")
