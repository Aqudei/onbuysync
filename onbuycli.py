from argparse import ArgumentParser
from decimal import Decimal
import json
import os
import re
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

PRODUCT_UPLOAD_BATCH_SIZE = 64
LISTING_BATCH_SIZE = 100

ONBUY_SITE_ID_UK = config('ONBUY_SITE_ID_UK')
ONBUY_SECRET_KEY = config('ONBUY_SECRET_KEY_TEST')
ONBUY_CONSUMER_KEY = config('ONBUY_CONSUMER_KEY_TEST')

CATEGORIES_MAPPING = "C:\\dev\\onbuysync\\data\\own-categories 7APR24.xlsx"

logger.info("ONBUY_SITE_ID_UK: {}".format(ONBUY_SITE_ID_UK))
logger.info("CATEGORIES_MAPPING: {}".format(CATEGORIES_MAPPING))

logger = logging.getLogger(__name__)

def chunk_df(df, chunk_size=32):
    chunks = [df[i:i+chunk_size] for i in range(0, len(df), chunk_size)]
    return chunks

class OnBuy():
    __queue_db = None
    __token = None
    __categories = {}
    __item_counter = 0

    def __init__(self, options) -> None:
        self.__options = options
        self.__token = None
        self.__categories = {}
        self.__queue_db = db.getDb("./data/results_db.json")
        
    def __pd_read(self,filename, dtype=None):
        
        _,ext = os.path.splitext(filename)
        if "CSV" in ext.upper():
            
            return pd.read_csv(filename,dtype=dtype)
        
        return pd.read_excel(filename,dtype=dtype)
    
    def __write_json(self,obj,filename):
        
        with open(filename,'wt') as outfile:
            outfile.write(json.dumps(obj,indent=4))
    
    
    def __load_products_df(self,product_feed):
        
        df_products = self.__pd_read(product_feed,dtype=str)
        df_products.columns = [c.upper() for c in df_products.columns]
                
        df_products['PRODUCT_FULLNAME'] = df_products['BRAND'] + " - " +  df_products['PRODUCT NAME'] + " - " + df_products['COLOR'] + ' - ' + df_products['GENDER']

        return df_products


    def __load_categories_df(self):
        
        df_category = self.__pd_read(CATEGORIES_MAPPING, dtype=str)
        df_category.columns = [c.upper() for c in  df_category.columns]
        return df_category
    
    def upload_products(self, products_feed):
        df_category = self.__load_categories_df()
        df_products = self.__load_products_df(products_feed) 
        
        dfg = df_products.groupby('PRODUCT_ID')
        
        products = list()
        
        for product_id, product_df in dfg:
            for idx,item in product_df.iterrows():
                category = df_category[(df_category['CATEGORY']==item['CATEGORY']) & \
                    (df_category['SUBCATEGORY']==item['SUBCATEGORY']) & \
                    (df_category['GENDER']==item['GENDER'])]
                
                if category.empty or pd.isna(category.iloc[0]['ONBUYCATEGORYID']):
                    logger.warning(f"Caregory <{item['CATEGORY']} - {item['SUBCATEGORY']} - {item['GENDER']}> Not Found!")
                    continue
                
                pictures = [
                    item['PICTURE_2'] or '',
                    item['PICTURE_3'] or '',
                    item['PICTURE_4'] or '',
                    item['PICTURE_5'] or '',    
                ]
                product_data = []
                if not pd.isna(item['SEASON']):
                    product_data.append({
                        "label":"SEASON",
                        "value": item['SEASON']
                    })
                    
                if not pd.isna(item['WEIGHT']):
                    product_data.append({
                        "label":"WEIGHT",
                        "value": item['WEIGHT']
                    })
                    
                product_item = {
                    'uid': int(item['MODEL_ID']),
                    "published": 1,
                    "category_id":int(category.iloc[0]['ONBUYCATEGORYID']),
                    "product_name": item['PRODUCT_FULLNAME'],
                    "product_codes":[
                        f"{item['BARCODE']}"  
                    ],
                    "description": item['DESCRIPTION'],
                    "brand_name": item['BRAND'],
                    "default_image": item['PICTURE_1'],
                    "additional_images": [p.strip() for p in pictures if p and p.strip() != ''],
                    "product_data":product_data,
                    "listings":{
                        "new": {
                            "sku": item["SKU"],
                            "price": float(item["PRICE"]),
                            "stock": int(item["QUANTITY"])
                        }
                    }
                }
                
                products.append(product_item)
            
            if len(products) >= PRODUCT_UPLOAD_BATCH_SIZE:
                # self.__write_json(products,"./data/payload.json")  
                self.__submit_to_onbuy_batch(products)
                products = list()
                        
        if len(products) > 0:
            self.__submit_to_onbuy_batch(products)

    def __submit_to_onbuy_batch(self,products):
        
        self.__item_counter += len(products)
        
        logger.info("Submitting products to OnBuy...")
                
        payload = json.dumps({
            "site_id": int(ONBUY_SITE_ID_UK),
            'products'  : products
        })
        
        with open("./data/last-payload.json",'wt') as outfile:
            outfile.write(payload)

        token = self.__get_onbuy_token()
        if not token:
            return
        
        url = 'https://api.onbuy.com/v2/products'
        
        headers = {
            'Authorization': token['access_token'],
            "Content-Type":"application/json"
        }
        
        response = requests.request("POST",url,headers=headers,data=payload)
        if response.status_code==200:
            result_items = response.json()['results']
            self.__write_results(result_items, "./data/upload-results.txt")
        else:
            logger.error("Submit OnBuy Result: {}\n{}".format(response.status_code,response.text))

        
        logger.info("Uploaded {} products...".format(self.__item_counter))
        
    def __write_results(self, results, filename):
        with open(filename,"a+",newline='\n') as outfile:
            for item in results:
                outfile.writelines([f"{datetime.datetime.now()},,, {json.dumps(item)}\n"])
                
    def __get_onbuy_token(self):
    
        if self.__token:
            expires_at_timestamp = int(self.__token['expires_at'])
            expires_at = datetime.datetime.fromtimestamp(expires_at_timestamp)
            
            delta = expires_at - datetime.datetime.now()
            
            if delta.total_seconds() > (5 * 60):
                return self.__token
        
        url = 'https://api.onbuy.com/v2/auth/request-token'
        payload={
            'secret_key': ONBUY_SECRET_KEY,
            'consumer_key': ONBUY_CONSUMER_KEY
        }
        
        response = requests.request("POST", url, data=payload)
        if response.status_code!=200:
            logger.error("Login Failed. Unable to fetch OnBuy Access Token.")
            logger.error(response.text)
            return
        
        
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


    def read_results_queue(self,results_file,product_feed):
        rgx = re.compile(r'Product\s+code\s+\"(.*)\"',re.I)
        products_df = self.__load_products_df(product_feed)
        categories_df = self.__load_categories_df()
        listings = []
        queue_ids = []
        
        batch = 50
                
        with  open(results_file,'rt',newline='\n') as infile:
            for line in infile.readlines():
                parts = re.split(",,,",line)
                data = json.loads(parts[-1])
                if data['success']:
                    queue_ids.append(data['queue_id'])

                
                if len(queue_ids) >= batch:
                    results = self.read_queues(queue_ids)
                    for r in results:
                        print(json.dumps(r))
                    
                    queue_ids = list()
                    
            if len(queue_ids) >= 0:
                results = self.read_queues(queue_ids)
                for r in results:
                    print(json.dumps(r))
                    
    def read_queues(self, queue_ids):
        
        logger.info("Reading queues...")
        url = 'https://api.onbuy.com/v2/queues'
        
        params = {
            "site_id" : ONBUY_SITE_ID_UK,
            "filter[queue_ids]" : ",".join(queue_ids)
        }
        
        token = self.__get_onbuy_token()
        if not token:
            return
        
        headers = {
            "Authorization" : token['access_token'],
            'Content-Type': 'application/json'
        }  
        
        response = requests.get(url,headers=headers,params=params)
        if response.status_code!=200:
            logger.error(response.text)
            return
        
        return response.json().get('results',[])
    
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
        if response.status_code!=200:
            logger.error("Status Code: {}, Response Text: {}".format(response.status_code,response.text))
        else:
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
    
    def search_product(self, product_code):
        logger.info("Looking up product with barcode: {}".format(product_code))
        
        url = "https://api.onbuy.com/v2/products"
        params = {
            "site_id":int(ONBUY_SITE_ID_UK),
            "filter[query]" : product_code,
            "filter[field]" : 'product_code',
            'limit':50,
            "offset":0
        }
        
        token = self.__get_onbuy_token()
        if not token:
            return
        
        headers = {
            'Authorization' : token['access_token']
        }
        
        response = requests.request("GET", url, headers=headers, params=params)

        if response.status_code!=200:
            return
        
        
        return response.json().get('results')
    
    def process_results(self,results_file, product_feed):
        rgx = re.compile(r'Product\s+code\s+\"(.*)\"',re.I)
        products_df = self.__load_products_df(product_feed)
        categories_df = self.__load_categories_df()
        listings = []
        
        with  open(results_file,'rt',newline='\n') as infile:
            for line in infile.readlines():
                parts = re.split(",,,",line)
                data = json.loads(parts[-1])
                error = data.get('error','')
                if 'already exists' in error:
                    opc = data['data']['existing_opc']
                    product_code = rgx.search(error).group(1)
                    product = products_df [products_df['BARCODE']==f"{product_code}"]
                    if product.empty:
                        logger.warning("Product not found in Feed, OPC: {}, BARCODE: {}".format(opc,product_code))
                        continue
                    
                    listings.append({
                        "opc": f"{opc}",
                        "condition": "new",
                        "sku": f"{product.iloc[0].SKU}",
                        "price": float(product.iloc[0].PRICE),
                        "stock": int(product.iloc[0].QUANTITY),
                        "delivery_weight": float(product.iloc[0].WEIGHT),
                        "handling_time": 4,
                        "manually_approve_listing": False
                    })          
                    
                if len(listings) >= LISTING_BATCH_SIZE:
                    self.__submit_listing(listings)
                    listings = list()
                
            if len(listings) >= 0:
                self.__submit_listing(listings)
                        

    def __submit_listing(self,listings):
        
        logger.info("Submitting listings...")
        self.__item_counter += len(listings)
        
        url = "https://api.onbuy.com/v2/listings"

        payload = json.dumps({
            "site_id": ONBUY_SITE_ID_UK,
            "listings": listings
        })
        
        token = self.__get_onbuy_token()
        if not token:
            return
        
        headers = {
            'Authorization': token['access_token'],
            'Content-Type': 'application/json'
        }

        response = requests.request("POST", url, headers=headers, data=payload)
        if response.status_code!=200:
            logger.error(response.text)
            return
        
        results = response.json().get('results',[])
        if len(results) > 0:
            self.__write_results(results,"./data/listing-results.txt")
            
        
        logger.info("Submitted listing items: {}".format(self.__item_counter))


    def update_prices(self,product_feed):
        url = "https://api.onbuy.com/v2/listings/by-sku"
        batch = 512
        
        product_df = self.__load_products_df(product_feed)
        my_listings_df = pd.read_csv("./data./my-listings.csv")
        my_listings_df.columns = [c.upper() for c in my_listings_df.columns]
        
        
        active_listing= pd.merge(product_df, my_listings_df, on='SKU', how='inner')
        chunks = chunk_df(active_listing,batch)
        token = self.__get_onbuy_token()
        if not token:
            return
        
        headers = {
            'Authorization': token['access_token'],
            'Content-Type': 'application/json'
        }
        
        for chunk in chunks:
            listings = []

            for _,item in chunk.iterrows():
                listings.append({
                    "sku": item.SKU,
                    "price": float(item.PRICE),
                    "stock": int(item.QUANTITY),
                })
                
            payload = json.dumps({
                "site_id": ONBUY_SITE_ID_UK,
                "listings": listings
            })
        
            response = requests.request("PUT", url, headers=headers, data=payload)
            logger.info(response.text)
            
    def dl_listings(self,out_filename):
        logger.info("Downloading OnBuy listings...")
        url = 'https://api.onbuy.com/v2/listings'
        params = {
            'site_id':int(ONBUY_SITE_ID_UK),
            'limit':50,
            'offset' : 0
        }
        
        token = self.__get_onbuy_token()
        if not token:
            return
        
        headers = {
            'Authorization' : token['access_token']
        }
    
        response = requests.request("GET", url, headers=headers, params=params)
        if response.status_code!=200:
            logger.error("Failed to download OnBuy listings..")
            logger.error(response.text)
            return
        
        
        self.__write_json(response.json().get('results'),out_filename)

        

if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--start-page",type=int,default=1)
    parser.add_argument("--upload-products", action='store_true')
    parser.add_argument("--update-prices")
    parser.add_argument("--product-feed")
    parser.add_argument("--list-queues")
    parser.add_argument("--read-results-queue")
    parser.add_argument("--delete-listings")
    parser.add_argument("--dl-listings")
    parser.add_argument("--find-product")
    parser.add_argument("--process-results")
    parser.add_argument("--live", action='store_true')
    
    options = parser.parse_args()
    
    if options.live:        
        logger.info("Running on LIVE Environment.")
        ONBUY_SECRET_KEY = config('ONBUY_SECRET_KEY_LIVE')
        ONBUY_CONSUMER_KEY = config('ONBUY_CONSUMER_KEY_LIVE')
    else:
        logger.info("Running on TEST Environment.")
        
    logger.info("ONBUY_SECRET_KEY: {}".format(ONBUY_SECRET_KEY))
    logger.info("ONBUY_CONSUMER_KEY: {}".format(ONBUY_CONSUMER_KEY))
    
    onbuy = OnBuy(options)
    
    if options.dl_listings:
        onbuy.dl_listings(options.dl_listings)
        
    if options.find_product:
        products = onbuy.search_product(options.find_product)
    
    if options.update_prices:
        products = onbuy.update_prices(options.update_prices)
        
    if options.process_results:
        if not options.product_feed:
            logger.error("Please provide Product Feed using [--product-feed] option.")
            exit(1)
            
        products = onbuy.process_results(options.process_results, options.product_feed)
        
    if options.list_queues:
        onbuy.list_queues(options.list_queues)
        
    if options.read_results_queue:
        onbuy.read_results_queue(options.read_results_queue,options.product_feed)
    
    if options.upload_products:
        onbuy.upload_products(options.product_feed)

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
            
            


