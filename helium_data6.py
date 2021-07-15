import requests
import pandas as pd
import numpy as np
import datetime as dt
import matplotlib.pyplot as plt
import streamlit as st 
import math
from scipy import spatial

#DOES NOT NEED TEAMS - CHECKS PASSWORD
def check_password():
    """Returns `True` if correct password is entered."""

    # Show text field for password.
    # You can move this anywhere on the page!
    password = st.sidebar.text_input("Password", type="password")
        
    # Check that it matches the stored password.
    if password:
        if password == st.secrets["password"]:
            return True
        else:
            st.sidebar.error("😕 Password incorrect")
    return False

headers = {}
def sending_request(url):
    r = requests.get(url=url, headers=headers)
    l = []
    data = r.json()
    l = data['data']
    while 'cursor' in data.keys():
        r = requests.get(url=url + '?cursor='+ data['cursor'], headers=headers)
        data = r.json()
        l += data['data']
    return l

nen = st.secrets['nen_account']
time_24_hrs_ago = (dt.datetime.now() - dt.timedelta(hours=24)).isoformat()
time_30_d_ago = (dt.datetime.now() - dt.timedelta(days=30)).isoformat()
assets = {}

for i in range(1,5000):
    digits = len(str(i))
    s = 'M' + '0'*(7-digits) + str(i)
    if s in st.secrets:
        assets[st.secrets[s]] = s

url = 'https://api.helium.io/v1/accounts/' + nen +'/hotspots'
data = sending_request(url)
new_hotspots = pd.DataFrame(data)
new_hotspots['asset id'] = new_hotspots['name'].map(assets)

options = []
new_hotspots['clntcity'] = [d.get('short_city').upper() for d in new_hotspots['geocode']]
new_hotspots['clntaddr1'] = [d.get('short_street') for d in new_hotspots['geocode']]
new_hotspots['cityid'] = [d.get('city_id') for d in new_hotspots['geocode']]

existing_hotspots = []
for c in list(set(new_hotspots['cityid'])):
    url = 'https://api.helium.io/v1/cities/'+ c + '/hotspots'
    existing_hotspots += sending_request(url)
existing_df = pd.DataFrame(existing_hotspots)
options = ['ALL'] + list(set(new_hotspots['clntcity']))

def cartesian(latitude, longitude, elevation = 0):
    # Convert to radians
    latitude = latitude * (math.pi / 180)
    longitude = longitude * (math.pi / 180)

    R = 6371 # 6378137.0 + elevation  # relative to centre of the earth
    X = R * math.cos(latitude) * math.cos(longitude)
    Y = R * math.cos(latitude) * math.sin(longitude)
    Z = R * math.sin(latitude)
    return (X, Y, Z)

places = []
for index, row in existing_df.iterrows():
    coordinates = [row['lat'], row['lng']]
    cartesian_coord = cartesian(*coordinates)
    places.append(cartesian_coord)

tree = spatial.KDTree(places)

def find_closest(lat, lon):
    cartesian_coord = cartesian(lat, lon)
    closest = tree.query([cartesian_coord], k =2, p = 2) #change k depending on how many neighbors want returned
    index = closest[1][0]
    return closest[0][0][1] * 1000

def get_mined(address, time = '2021-06-01T00:00:00'):
    if time != '2021-06-01T00:00:00':  
        t = repr(time).replace('\'','')
    else:
        t = time
    url = 'https://api.helium.io/v1/hotspots/' + address + '/rewards/sum' + '?min_time=' + t
    total_mined = sending_request(url)['total']
    return total_mined
def get_cities(city):
    cities = {}
    df = new_hotspots
    for idx, row in df.iterrows():
        if row['clntcity'] not in cities.keys():
            cities[row['clntcity']] = []
        status = row['status']['online']
        day_earnings = get_mined(row['address'], time_24_hrs_ago)
        month_earnings = get_mined(row['address'], time_30_d_ago)
        total_earnings = get_mined(row['address'])

        d = {'name': row['name'].replace("-", " "),'location':row['clntaddr1'], 'status': status, 'day earnings': day_earnings, 'month earnings': month_earnings, 'total earnings': total_earnings}
        cities[row['clntcity']].append(d)
    return cities

def compiled():
    existing_df['30d earnings'] = existing_df.apply(lambda x: get_mined(x['address'], time_30_d_ago), axis = 1)
    existing_df['City'] = [d.get('long_city').upper() for d in existing_df['geocode']]

    data = get_cities('ALL')
    total = []
    for key in data.keys():
        offline = 0
        day_earnings = 0
        month_earnings = 0
        total_earnings = 0 
        num_hotspots = len(data[key])
        for hotspot in data[key]:
            if hotspot['status'] == 'offline':
                offline +=1
            day_earnings += hotspot['day earnings']
            month_earnings += hotspot['month earnings']
            total_earnings += hotspot['total earnings']
        curr_city = existing_df[existing_df['City'] == key]
        d = {'city': key, '# hotspots': num_hotspots, '# offline': offline, '24hr earnings': day_earnings, '30d earnings': month_earnings, 'avg 30d earnings': month_earnings/num_hotspots,'city avg 30d earnings': round(curr_city['30d earnings'].sum()/len(curr_city),2),'total earnings': total_earnings}
        total.append(d)
    df = pd.DataFrame(total).sort_values(by= 'total earnings', ascending = False)
    d = dict(df.sum(axis =0, numeric_only = True))
    d['city'] = 'TOTAL'
    df = df.append(d, ignore_index = True)
    data_types_dict = {'city':str, '# hotspots': int, '# offline': int, 'city avg 30d earnings':float}
    df = df.astype(data_types_dict)
    df.loc[df.city == 'TOTAL','city avg 30d earnings'] = ' '
    df.loc[df.city == 'TOTAL','avg 30d earnings'] = ' '

    return df  

def activity_count(address):
    url = 'https://api.helium.io/v1/hotspots/' + address + '/activity/count'
    return sending_request(url)

def color_status(val):
    if type(val) == float:
        if val < 300:
            color = 'tomato'
        elif val < 500 and val > 300:
            color = 'yellow'
        else: 
            color = 'white'
        return f'background-color:{color}'
    else:  
        if val == 'online':
            color = 'lightgreen'
        elif val == 'offline':
            color = 'tomato'
        elif val == ' ':
            color = 'lightsteelblue'
        elif val == '  ':
            color = 'white'
        else:
            color = 'white'
        return f'background-color:{color}'

def stats(city_name):
    if city_name == 'ALL':
        cit = new_hotspots
    else:
        cit = new_hotspots[new_hotspots['clntcity'] == city_name]

    witness = []
    for idx, row in cit.iterrows():
        url = 'https://api.helium.io/v1/hotspots/' + row['address'] + '/witnesses'
        data = sending_request(url)
        recent_witnesses = len(data)
        
        d = activity_count(row['address'])
        d['name'] = row['name'].replace("-", " ")
        d['location'] = row['clntaddr1']
        d['asset id'] = row['asset id']
        d['city'] = row['clntcity']
        d['status'] = row['status']['online']
        d['reward scale'] = row['reward_scale']

        d['total mined'] = get_mined(row['address'], '2021-06-01T00:00:00')
        d['day earnings'] = get_mined(row['address'], time_24_hrs_ago)
        d['month earnings'] = get_mined(row['address'], time_30_d_ago)

        d['closest hotspot (m)'] = round(find_closest(row['lat'], row['lng']),2)
        
        d['recent witnesses'] = recent_witnesses
        witness.append(d)
        
    df = pd.DataFrame(witness).sort_values(by= 'total mined', ascending = False)
    
    cols = ['name','location','asset id','city', 'status','day earnings', 'month earnings','total mined','reward scale','closest hotspot (m)','recent witnesses']
    
    d_total = dict(df.sum(axis =0, numeric_only = True))
    d_total['name'] = 'TOTAL'
    d_total['location'] = " "
    d_total['status'] = " "
    d_total['asset id'] = " "
    d_total['city'] = " "
    d_total['reward scale'] = " "
    d_total['closest hotspot (m)'] = " "

    d = dict(df.mean(axis =0, numeric_only = True))
    d['name'] = 'AVERAGE'
    d['location'] = " "
    d['status'] = "  "
    d['asset id'] = " "
    d['city'] = " "
    d['reward scale'] = " "
    
    df = df.append(d, ignore_index = True)  
    df = df.append(d_total, ignore_index = True)
    return df[cols].loc[:, (df != 0).any(axis=0)]

if check_password():
    st.sidebar.write("## Helium Hotspots")
    page = st.sidebar.selectbox("App Navigation", ["Hotspot Data", "Earnings Data"])

    if page == 'Hotspot Data':
        city_name = st.sidebar.selectbox('Choose a city' ,options)
        filt = st.sidebar.selectbox('Filter Online/Offline', ['All', 'Online','Offline'])
        hot_data = stats(city_name).set_index('name')
        if filt == 'Online':
            hot_data = hot_data[hot_data['status']== 'online']
        elif filt == 'Offline':
            hot_data = hot_data[hot_data['status']== 'offline']
        hot_data = hot_data.style.apply(lambda x: ['background: lightsteelblue' if x.name == 'TOTAL' else '' for i in x], axis=1)
        st.table(hot_data.applymap(color_status, subset=['status', 'closest hotspot (m)']).set_precision(2))
        
        st.text('*total earnings are calculated starting from june 1')
    if page == 'Earnings Data':
        cities = compiled().set_index('city')
        st.table(cities.style.apply(lambda x: ['background: lightsteelblue' if x.name == 'TOTAL' else '' for i in x], axis=1).set_precision(2))


