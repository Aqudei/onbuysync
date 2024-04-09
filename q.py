import datetime
import pandas as pd
from decouple import config
import logging
import requests

# Create a logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Create file handler
file_handler = logging.FileHandler("debug2.log")
file_handler.setLevel(logging.DEBUG)

# Create console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# Create formatter and add it to the handlers
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# Add the handlers to the logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)

CATEGORIES_PATH = "C:\\dev\\onbuysync\\data\\own-categories 7APR24.xlsx"
PRODUCT_FEED_PATH = "C:\\dev\\onbuysync\\data\\ONBUY PRODUCT DATA FEED - 3 APR 2024.xlsx"

PRODUCT_UPLOAD_BATCH_SIZE = 5

WOOCOMMERCE_API_VERSION = config('WOOCOMMERCE_API_VERSION')
ONBUY_SITE_ID_UK = config('ONBUY_SITE_ID_UK')
ONBUY_SECRET_KEY = config('ONBUY_SECRET_KEY_TEST')
ONBUY_CONSUMER_KEY = config('ONBUY_CONSUMER_KEY_TEST')

categories_df = pd.read_excel(CATEGORIES_PATH,dtype=str)
products_df = pd.read_excel(PRODUCT_FEED_PATH)

products_df['ProductName'] = products_df['Brand'] + ' ' + products_df['Name']


__token = None

def __get_onbuy_token():
    
    global __token
    
    if __token:
        expires_at_timestamp = int(__token['expires_at'])
        expires_at = datetime.datetime.fromtimestamp(expires_at_timestamp)
        
        delta = expires_at - datetime.datetime.now()
        
        if delta.total_seconds() > 60:
            return __token
    
    url = 'https://api.onbuy.com/v2/auth/request-token'
    payload={
        'secret_key': ONBUY_SECRET_KEY,
        'consumer_key': ONBUY_CONSUMER_KEY
    }
    
    response = requests.request("POST", url, data=payload)
    print(response.text)
    
    __token = response.json()
    
    return __token

def browse_variants(category_id):
    url = f"https://api.onbuy.com/v2/categories/{category_id}/variants"
    params = {
        "site_id":ONBUY_SITE_ID_UK,
        "limit":25,
        "offset":0
    }
    
    token = __get_onbuy_token()
    
    headers = {
        "Authorization":token['access_token']
    }
    
    response = requests.get(url,headers=headers,params=params)
    if response.status_code != 200:
        logger.error(response.text)
        return
    
    import pdb; pdb.set_trace()

    return response.json()['results']

for product_id, items in products_df.groupby("Product_id"):
    products = list()
    for i, item in items.iterrows():
        filter = (categories_df['Category']==item.Category) & (categories_df['Subcategory']==item.Subcategory) & \
            (categories_df['Gender']==item.Gender)    
        category = categories_df[filter]
        
        if category.empty:
            continue
        
        
        variants = browse_variants(category.iloc[0].OnBuyCategoryID)
        data = {
            "uid": int(product_id),
            "category_id": f"{category.iloc[0].OnBuyCategoryID}",
            "published": "1",
            "product_name": item.ProductName,
            "product_codes":  ["{}".format(b) for b in items["Barcode"]],
            "description": item.Description,
            "brand_name": item.Brand,
            "default_image": item.Picture_1,
            "product_data": [
                {
                    "label": "Season",
                    "value": item.Season
                }
            ],
            "variant_1": {
                "feature_id": 102
            },
        },
        
        import pdb; pdb.set_trace()

        products.append(data)
    