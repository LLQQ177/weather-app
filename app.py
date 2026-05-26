from flask import Flask, render_template, request
import requests
import time

app = Flask(__name__)

# 和风天气 Key
API_KEY = "b12cb6295d604e7aaafdda96fe9aaaf5"
API_HOST="p23aaqvmyb.re.qweatherapi.com"
# 简单缓存
weather_cache = {}
forecast_cache = {}
CACHE_DURATION = 600  # 10分钟

# 天气背景判断
def get_bg_class(desc):
    if "雷" in desc or "暴" in desc:
        return "thunderstorm"
    elif "雾" in desc or "霾" in desc:
        return "foggy"
    elif "雪" in desc:
        return "snowy"
    elif "雨" in desc:
        return "rainy"
    elif "阴" in desc:
        return "overcast"
    elif "云" in desc:
        return "cloudy"
    elif "晴" in desc:
        return "sunny"
    elif "风" in desc:
        return "windy"
    else:
        return "default"

#穿衣建议
def get_clothing_suggestion(temp, desc, humidity):
    #根据温度、天气描述和湿度给出穿衣建议

    # 温度分层
    if temp <= 0:
        temp_level = "freezing"
    elif temp <= 10:
        temp_level = "cold"
    elif temp <= 20:
        temp_level = "cool"
    elif temp <= 28:
        temp_level = "warm"
    else:
        temp_level = "hot"

    # 天气特殊处理
    is_rain = "雨" in desc
    is_snow = "雪" in desc
    is_windy = "风" in desc

    # 基础建议
    suggestions = {
        "freezing": "❄️ 极寒天气！建议：羽绒服+厚毛衣+围巾手套+保暖内衣",
        "cold": "🧥 天气寒冷，建议：棉衣/羽绒服+毛衣+长裤",
        "cool": "🧥 气温偏凉，建议：外套+长袖+长裤",
        "warm": "👕 天气温暖，建议：长袖T恤+薄外套或单穿长袖",
        "hot": "🩳 天气炎热，建议：短袖+短裤/裙子+注意防晒"
    }

    # 根据天气调整
    extra_tips = []

    if is_rain:
        extra_tips.append("🌂 记得带伞！")
        if temp_level in ["cold", "freezing"]:
            extra_tips.append("💧 雨天湿冷，注意防寒")
    elif is_snow:
        extra_tips.append("☃️ 雪天路滑，穿防滑鞋")
    elif is_windy:
        extra_tips.append("💨 风大，建议防风外套")

    # 湿度提示
    if humidity >= 80:
        extra_tips.append("💦 湿度较高，注意除湿防潮")
    elif humidity <= 30:
        extra_tips.append("🔥 空气干燥，多喝水补水")

    suggestion = suggestions[temp_level]
    if extra_tips:
        suggestion += "\n💡 " + " ".join(extra_tips)

    return suggestion

# 查当前天气
def get_weather(city):
    now = time.time()
    if city in weather_cache:
        data, ts = weather_cache[city]
        if now - ts < CACHE_DURATION:
            return data

    # 第一步：城市名 → 城市 ID
    geo_url = f"https://{API_HOST}/geo/v2/city/lookup?location={city}&key={API_KEY}"
    try:
        geo_resp = requests.get(geo_url)
        geo_data = geo_resp.json()
        if geo_data["code"] != "200" or not geo_data["location"]:
            return None
        city_id = geo_data["location"][0]["id"]
        city_name = geo_data["location"][0]["name"]
    except:
        return None

    # 第二步：城市 ID → 实时天气
    weather_url = f"https://{API_HOST}/v7/weather/now?location={city_id}&key={API_KEY}&lang=zh"
    try:
        resp = requests.get(weather_url)
        data = resp.json()
        if data["code"] != "200":
            return None
        now_data = data["now"]
        result = {
            "city": city_name,
            "desc": now_data["text"],
            "temp": int(now_data["temp"]),
            "feels_like": int(now_data["feelsLike"]),
            "humidity": int(now_data["humidity"]),
            "bg_class": get_bg_class(now_data["text"])
        }
        weather_cache[city] = (result, now)
        return result
    except:
        return None

# 查未来预报
def get_forecast(city):
    now = time.time()
    if city in forecast_cache:
        data, ts = forecast_cache[city]
        if now - ts < CACHE_DURATION:
            return data

    # 第一步：城市名 → 城市 ID
    geo_url = f"https://{API_HOST}/geo/v2/city/lookup?location={city}&key={API_KEY}"
    try:
        geo_resp = requests.get(geo_url)
        geo_data = geo_resp.json()
        if geo_data["code"] != "200" or not geo_data.get("location"):
            return None
        city_id = geo_data["location"][0]["id"]
    except Exception as e:
        print(f"Geo error: {e}")
        return None

    # 第二步：使用城市ID获取7天预报
    forecast_url = f"https://{API_HOST}/v7/weather/7d?location={city_id}&key={API_KEY}&lang=zh"
    try:
        resp = requests.get(forecast_url)
        data = resp.json()

        if data["code"] != "200":
            print(f"Forecast API error: {data}")
            return None

        daily = {}
        for day in data["daily"]:
            daily[day["fxDate"]] = {
                "desc": day["textDay"],
                "temp_min": int(day["tempMin"]),
                "temp_max": int(day["tempMax"]),
                "bg_class": get_bg_class(day["textDay"])
            }
        forecast_cache[city] = (daily, now)
        return daily
    except Exception as e:
        print(f"Forecast error: {e}")
        return None

# 主页面
@app.route("/", methods=["GET", "POST"])
def home():
    weather = None
    forecast_dates = []
    selected_date = ""
    selected_forecast = None
    error = None
    city = ""

    if request.method == "POST":
        city = request.form.get("city", "").strip()
        selected_date = request.form.get("forecast_date", "").strip()

        if city:
                weather = get_weather(city)
    if weather:
        weather["clothing"] = get_clothing_suggestion(weather["temp"], weather["desc"], weather["humidity"])
        forecast_dict = get_forecast(city)
        if forecast_dict:
            forecast_dates = sorted(forecast_dict.keys())
            if selected_date in forecast_dict:
                selected_forecast = forecast_dict[selected_date]

                selected_forecast["clothing"] = get_clothing_suggestion(
                    (selected_forecast["temp_min"] + selected_forecast["temp_max"]) // 2,
                    selected_forecast["desc"],
                    60  # 默认湿度
                )
    if city:
      weather = get_weather(city)
      if not weather:  # 如果查询失败
        error = "查不到该城市，请检查城市名" 

    return render_template("index.html",
                           weather=weather,
                           forecast_dates=forecast_dates,
                           selected_date=selected_date,
                           selected_forecast=selected_forecast,
                           error=error,
                           city=city)

if __name__ == "__main__":
    app.run(debug=True)