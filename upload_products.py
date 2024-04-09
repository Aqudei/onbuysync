from argparse import ArgumentParser
from decimal import Decimal
import json
import os
import time
import traceback as tb
import logging
import uuid 
import requests
from woocommerce import API
from decouple import config
import logging
import datetime
import pandas as pd
from pysondb import db


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

queue_db = db.getDb("./data/queues.json")

PRODUCT_UPLOAD_BATCH_SIZE = 4

ONBUY_SITE_ID_UK = config('ONBUY_SITE_ID_UK')
ONBUY_SECRET_KEY = config('ONBUY_SECRET_KEY_TEST')
ONBUY_CONSUMER_KEY = config('ONBUY_CONSUMER_KEY_TEST')

CATEGORIES_MAPPING = "C:\\dev\\onbuysync\\data\\own-categories 7APR24.xlsx"

logger = logging.getLogger(__name__)

def chunk_df(df, chunk_size=32):
    chunks = [df[i:i+chunk_size] for i in range(0, len(df), chunk_size)]
    return chunks

class OnBuy():
    
    __token = None
    __categories = {}
    
    def __init__(self, options) -> None:
        self.__options = options

    def __pd_read(self,filename, dtype=None):
        
        _,ext = os.path.splitext(filename)
        if "CSV" in ext.upper():
            
            return pd.read_csv(filename,dtype=dtype)
        
        return pd.read_excel(filename,dtype=dtype)
    
    def __write_json(self,obj,filename):
        
        with open(filename,'wt') as outfile:
            outfile.write(json.dumps(obj,indent=4))
            
    def upload_products(self, products_feed):
        df_category = self.__pd_read(CATEGORIES_MAPPING, dtype=str)
        df_category.columns = [c.upper() for c in  df_category.columns]
        df_products = self.__pd_read(products_feed,dtype=str)
        df_products.columns = [c.upper() for c in df_products.columns]
        
        df_products['PRODUCT_FULLNAME'] = df_products['BRAND'] + " - " +  df_products['PRODUCT NAME'] + " - " + df_products['COLOR'] + ' - ' + df_products['GENDER']
        dfg = df_products.groupby('PRODUCT_ID')
        products = list()
        for product_id, product_df in dfg:
            for idx,item in product_df.iterrows():
                category = df_category[(df_category['CATEGORY']==item['CATEGORY']) & \
                    (df_category['SUBCATEGORY']==item['SUBCATEGORY']) & \
                    (df_category['GENDER']==item['GENDER'])]
                
                if category.empty:
                    continue
                
                pictures = [
                    item['PICTURE_2'] or '',
                    item['PICTURE_3'] or '',
                    item['PICTURE_4'] or '',
                    item['PICTURE_5'] or '',    
                ]
                
                product_data = {
                    'uid': int(item['MODEL_ID']),
                    "published": "1",
                    "live": "1",
                    "category_id":f"{category.iloc[0]['ONBUYCATEGORYID']}",
                    "product_name": item['PRODUCT_FULLNAME'],
                    "product_codes":[
                        f"{item['BARCODE']}"  
                    ],
                    "description": item['DESCRIPTION'],
                    "brand_name": item['BRAND'],
                    "default_image": item['PICTURE_1'],
                    "additional_images": [p.strip() for p in pictures if p and p.strip() != ''],
                    "product_data":[
                        {
                            "label":"SEASON",
                            "value": item['SEASON']
                        },
                        {
                            "label":"GENDER",
                            "value": item['GENDER']
                        },
                        {
                            "label":"Weight",
                            "value": item['WEIGHT']
                        }
                    ],
                    "listings": {
                        "new": {
                            "sku": item['SKU'],
                            "stock": int(item['QUANTITY']),
                        }
                    }
                }
                
                products.append(product_data)
            
            if len(products) >= PRODUCT_UPLOAD_BATCH_SIZE:
                # self.__write_json(products,"./data/payload.json")  
                self.__submit_to_onbuy(products)
                products = list()
        
        if len(products) > 0:
            self.__submit_to_onbuy(products)

            
    def __submit_to_onbuy(self,products):
        logger.info("Submitting products to OnBuy...")
        payload = json.dumps({
            "site_id": int(ONBUY_SITE_ID_UK),
            'products'  : products
        })
        
        with open("./data/last-payload.json",'wt') as outfile:
            outfile.write(payload)

        token = self.__get_onbuy_token()
        url = 'https://api.onbuy.com/v2/products'
        headers = {
            'Authorization': token['access_token'],
            'Content-Type': 'application/json'
        }
        
        response = requests.request("POST", url,headers=headers,data=payload)
        if response.status_code==200:
            result_items = response.json()['results']
            queue_db.addMany(result_items)
        else:
            logger.error("Submit OnBuy result: {}\n{}".format(response.status_code,response.text))

    def __get_onbuy_token(self):
    
        if self.__token:
            expires_at_timestamp = int(self.__token['expires_at'])
            expires_at = datetime.datetime.fromtimestamp(expires_at_timestamp)
            
            delta = expires_at - datetime.datetime.now()
            
            if delta.total_seconds() > 60:
                return self.__token
        
        url = 'https://api.onbuy.com/v2/auth/request-token'
        payload={
            'secret_key': ONBUY_SECRET_KEY,
            'consumer_key': ONBUY_CONSUMER_KEY
        }
        
        response = requests.request("POST", url, data=payload)
        print(response.text)
        
        self.__token = response.json()
        
        return self.__token
    
    
    def __find_category_by_name(self,partial_name):

        token = self.__get_onbuy_token()
        url = "https://api.onbuy.com/v2/categories"
        params = {
            'site_id': ONBUY_SITE_ID_UK,
            'filter[can_list_in]' : '1',
            'filter[name]' : partial_name,
        }
        
        headers = {
            'Authorization' : token['access_token']
        }
        
        response = requests.get(url,params=params, headers=headers)
        results = response.json()['results']
        if len(results) <= 0:
            logger.warning("Unable to find category of {}".format(partial_name))
            return None,None
        
        category = results[0]
        category_id = category.get('category_id')
        return category_id, category


    def read_queue(self, queue_id):
        logger.info("Reading queue {}".format(queue_id))
        url = 'https://api.onbuy.com/v2/queues/{}'.format(queue_id)
        params = {
            "site_id" : ONBUY_SITE_ID_UK,
            "queue_id" : queue_id
        }
        token = self.__get_onbuy_token()
        
        headers = {
            "Authorization" : token['access_token'],
            'Content-Type': 'application/json'
        }  
        
        response = requests.get(url,headers=headers,params=params)
        if response.status_code==200:
            self.__write_json(response.json(),"./data/queue-{}.json".format(queue_id))
        
        
        logger.debug(response.text)
        
    def list_queues(self, status):
        url ="https://api.onbuy.com/v2/queues"
        params = {
            "site_id" : ONBUY_SITE_ID_UK,
            'filter[status]' : status,
            'limit':100
        }
        token = self.__get_onbuy_token()
        headers = {
            "Authorization" : token['access_token'],
            'Content-Type': 'application/json'
        } 
        
        response = requests.get(url,headers=headers,params=params)
        if response.status_code==200:
            self.__write_json(response.json(),"./data/queues.json")
        
    def delete_listings(self,skus):
        logger.info("Deleting product listings...")
        url = 'https://api.onbuy.com/v2/listings/by-sku'

        payload = json.dumps({
            "site_id": ONBUY_SITE_ID_UK,
            "skus": skus
        })
        
        token = self.__get_onbuy_token()

        headers = {
            'Authorization': token['access_token'],
            'Content-Type': 'application/json'
        }

        response = requests.request("DELETE", url, headers=headers, data=payload)
        if not response.status_code==200:
            logger.error(response.text)
            with open("./data/last_error.html",'wt') as outfile:
                outfile.write(response.text)
                    
            
    def __find_category(self,category_search):
        if category_search in self.__categories:
            category_id,category = self.__categories[category_search] 
            return category_id
        
        token = self.__get_onbuy_token()
        url = "https://api.onbuy.com/v2/categories"
        params = {
            'site_id': ONBUY_SITE_ID_UK,
            'filter[can_list_in]' : '1',
            'filter[search]' : category_search,
        }
        
        headers = {
            'Authorization' : token['access_token']
        }
        
        response = requests.get(url,params=params, headers=headers)
        results = response.json()['results']
        if len(results) <= 0:
            cat_id,cat = self.__find_category_by_name(category_search.split(">")[0].strip())
            
            if not cat_id:
                logger.warning("Unable to find category of {}".format(category_search))
                self.__categories[category_search.strip()] = None, None
                return None
            else:
                self.__categories[category_search.strip()] = cat_id,cat
                return cat_id
        
        category = results[0]
        category_id = category.get('category_id')
        self.__categories[category_search.strip()] = category_id, category
        return category_id
            
    

if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--start-page",type=int,default=1)
    parser.add_argument("--upload-products")
    parser.add_argument("--list-queues")
    parser.add_argument("--read-queue")
    parser.add_argument("--delete-listings")

    options = parser.parse_args()
    
    onbuy = OnBuy(options)
    
    if options.list_queues:
        onbuy.list_queues(options.list_queues)
        
    if options.read_queue:
        onbuy.read_queue(options.read_queue)
    
    if options.upload_products:
        onbuy.upload_products(options.upload_products)

    if options.delete_listings:
        listings_file = options.delete_listings
        _,ext = os.path.splitext(listings_file)
        if 'CSV' in ext.upper():
            df = pd.read_csv(listings_file)
        else:
            df = pd.read_excel(listings_file)
        
        chunks = chunk_df(df,800)
        for chunk in chunks:
            onbuy.delete_listings([sku for sku in chunk['sku']])
            
            


