"""Sample listing data for seeding the database."""

SAMPLE_LISTINGS = [
    # Moscow — Sale
    {"city": "Москва", "district": "Центральный", "address": "ул. Тверская, 15", "rooms": 2, "area_m2": 65, "floor": 5, "floors_total": 12, "price": 18500000, "deal_type": "sale", "property_type": "apartment", "description": "Уютная 2-комнатная квартира в центре Москвы. Свежий ремонт, панорамные окна."},
    {"city": "Москва", "district": "Арбат", "address": "ул. Арбат, 25", "rooms": 3, "area_m2": 95, "floor": 8, "floors_total": 15, "price": 35000000, "deal_type": "sale", "property_type": "apartment", "description": "Просторная трёшка в историческом центре. Высокие потолки, паркет."},
    {"city": "Москва", "district": "Пресненский", "address": "Пресненская наб., 12", "rooms": 1, "area_m2": 42, "floor": 22, "floors_total": 55, "price": 12000000, "deal_type": "sale", "property_type": "apartment", "description": "Студия в Москва-Сити. Вид на город, мебель включена."},
    {"city": "Москва", "district": "Хамовники", "address": "ул. Льва Толстого, 7", "rooms": 4, "area_m2": 150, "floor": 3, "floors_total": 6, "price": 65000000, "deal_type": "sale", "property_type": "apartment", "description": "Элитная 4-комнатная квартира. Дизайнерский ремонт, камин."},
    {"city": "Москва", "district": "Раменки", "address": "ул. Раменки, 18", "rooms": 3, "area_m2": 85, "floor": 12, "floors_total": 25, "price": 22000000, "deal_type": "sale", "property_type": "apartment", "description": "Просторная трёшка в новостройке. Паркинг включён."},
    # Moscow — Rent
    {"city": "Москва", "district": "Таганский", "address": "ул. Марксисткая, 3", "rooms": 2, "area_m2": 58, "floor": 9, "floors_total": 17, "price": 75000, "deal_type": "rent", "property_type": "apartment", "description": "Сдаётся 2-комнатная квартира. Все удобства, техника."},
    {"city": "Москва", "district": "Басманный", "address": "ул. Покровка, 22", "rooms": 1, "area_m2": 38, "floor": 4, "floors_total": 9, "price": 55000, "deal_type": "rent", "property_type": "apartment", "description": "Однокомнатная квартира рядом с метро. Свежий ремонт."},
    {"city": "Москва", "district": "Якиманка", "address": "ул. Большая Полянка, 44", "rooms": 0, "area_m2": 28, "floor": 11, "floors_total": 20, "price": 45000, "deal_type": "rent", "property_type": "studio", "description": "Студия с панорамным видом. Полностью меблирована."},
    # Saint Petersburg — Sale
    {"city": "Санкт-Петербург", "district": "Адмиралтейский", "address": "Невский пр., 78", "rooms": 2, "area_m2": 70, "floor": 4, "floors_total": 5, "price": 15000000, "deal_type": "sale", "property_type": "apartment", "description": "Квартира на Невском. Исторический дом, лепнина, высокие потолки."},
    {"city": "Санкт-Петербург", "district": "Петроградский", "address": "Каменноостровский пр., 40", "rooms": 1, "area_m2": 45, "floor": 6, "floors_total": 8, "price": 9500000, "deal_type": "sale", "property_type": "apartment", "description": "Однушка на Петроградке. Рядом метро и парк."},
    {"city": "Санкт-Петербург", "district": "Василеостровский", "address": "Средний пр. В.О., 28", "rooms": 3, "area_m2": 90, "floor": 3, "floors_total": 4, "price": 20000000, "deal_type": "sale", "property_type": "apartment", "description": "Трёшка на Васильевском острове. Вид на Неву."},
    # Saint Petersburg — Rent
    {"city": "Санкт-Петербург", "district": "Центральный", "address": "ул. Рубинштейна, 15", "rooms": 2, "area_m2": 62, "floor": 5, "floors_total": 6, "price": 65000, "deal_type": "rent", "property_type": "apartment", "description": "Сдаётся квартира на улице ресторанов. Отличное состояние."},
    {"city": "Санкт-Петербург", "district": "Московский", "address": "Московский пр., 100", "rooms": 0, "area_m2": 30, "floor": 10, "floors_total": 18, "price": 35000, "deal_type": "rent", "property_type": "studio", "description": "Студия у метро. Подходит для одного."},
    # Krasnodar
    {"city": "Краснодар", "district": "Центральный", "address": "ул. Красная, 170", "rooms": 2, "area_m2": 60, "floor": 7, "floors_total": 16, "price": 8500000, "deal_type": "sale", "property_type": "apartment", "description": "Двушка в центре Краснодара. Новостройка, чистовая отделка."},
    {"city": "Краснодар", "district": "Западный", "address": "ул. Западная, 45", "rooms": 3, "area_m2": 88, "floor": 3, "floors_total": 9, "price": 11000000, "deal_type": "sale", "property_type": "apartment", "description": "Просторная трёшка с видом на парк. Два санузла."},
    {"city": "Краснодар", "district": "Прикубанский", "address": "ул. Ставропольская, 200", "rooms": 1, "area_m2": 40, "floor": 5, "floors_total": 10, "price": 5500000, "deal_type": "sale", "property_type": "apartment", "description": "Однокомнатная квартира. Тихий двор, детская площадка."},
    {"city": "Краснодар", "district": "Фестивальный", "address": "ул. Кубанская, 10", "rooms": 4, "area_m2": 120, "floor": 2, "floors_total": 3, "price": 18000000, "deal_type": "sale", "property_type": "house", "description": "Частный дом с участком 6 соток. Гараж, баня, бассейн."},
    # Sochi
    {"city": "Сочи", "district": "Центральный", "address": "ул. Навагинская, 12", "rooms": 2, "area_m2": 55, "floor": 8, "floors_total": 14, "price": 12000000, "deal_type": "sale", "property_type": "apartment", "description": "Квартира с видом на море. 5 минут до пляжа."},
    {"city": "Сочи", "district": "Хостинский", "address": "ул. Черноморская, 5", "rooms": 1, "area_m2": 35, "floor": 4, "floors_total": 5, "price": 40000, "deal_type": "rent", "property_type": "apartment", "description": "Сдаётся на лето. Вид на море, кондиционер, Wi-Fi."},
    {"city": "Сочи", "district": "Адлер", "address": "ул. Ленина, 215", "rooms": 0, "area_m2": 25, "floor": 9, "floors_total": 12, "price": 6000000, "deal_type": "sale", "property_type": "studio", "description": "Студия в 3 минутах от олимпийского парка. С мебелью."},
    # Ekaterinburg
    {"city": "Екатеринбург", "district": "Ленинский", "address": "ул. Малышева, 36", "rooms": 2, "area_m2": 55, "floor": 10, "floors_total": 20, "price": 7500000, "deal_type": "sale", "property_type": "apartment", "description": "Двушка в центре Екб. Панорамные окна, вид на город."},
    {"city": "Екатеринбург", "district": "Октябрьский", "address": "ул. 8 Марта, 50", "rooms": 1, "area_m2": 38, "floor": 3, "floors_total": 5, "price": 35000, "deal_type": "rent", "property_type": "apartment", "description": "Сдаётся однушка. Рядом ТЦ и парк."},
    # Novosibirsk
    {"city": "Новосибирск", "district": "Центральный", "address": "Красный пр., 25", "rooms": 2, "area_m2": 60, "floor": 6, "floors_total": 9, "price": 6500000, "deal_type": "sale", "property_type": "apartment", "description": "Квартира на Красном проспекте. Свежий ремонт."},
    {"city": "Новосибирск", "district": "Советский", "address": "ул. Ипподромская, 42", "rooms": 3, "area_m2": 80, "floor": 4, "floors_total": 10, "price": 9000000, "deal_type": "sale", "property_type": "apartment", "description": "Трёшка в тихом районе. Рядом Академгородок."},
    # Commercial
    {"city": "Москва", "district": "Пресненский", "address": "Пресненская наб., 8", "rooms": None, "area_m2": 200, "floor": 15, "floors_total": 55, "price": 500000, "deal_type": "rent", "property_type": "commercial", "description": "Офис класса А в Москва-Сити. Панорамное остекление."},
    {"city": "Санкт-Петербург", "district": "Невский", "address": "Невский пр., 100", "rooms": None, "area_m2": 80, "floor": 1, "floors_total": 5, "price": 150000, "deal_type": "rent", "property_type": "commercial", "description": "Торговое помещение на Невском. Высокий трафик."},
    # Land
    {"city": "Краснодар", "district": "Пашковский", "address": "ст. Пашковская", "rooms": None, "area_m2": 1500, "floor": None, "floors_total": None, "price": 3500000, "deal_type": "sale", "property_type": "land", "description": "Участок 15 соток. Все коммуникации, асфальтированный подъезд."},
]
