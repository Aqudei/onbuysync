from argparse import ArgumentParser
from decimal import Decimal
import time
import traceback as tb
import logging
import uuid 
import requests
from woocommerce import API
from decouple import config
import logging
import datetime

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


WOOCOMMERCE_API_URL = config('WOOCOMMERCE_API_URL')
WOOCOMMERCE_CONSUMER_KEY = config('WOOCOMMERCE_CONSUMER_KEY')
WOOCOMMERCE_CONSUMER_SECRET = config('WOOCOMMERCE_CONSUMER_SECRET')
WOOCOMMERCE_API_VERSION = config('WOOCOMMERCE_API_VERSION')
ONBUY_SITE_ID_UK = config('ONBUY_SITE_ID_UK')
ONBUY_SECRET_KEY_LIVE = config('ONBUY_SECRET_KEY_LIVE')
ONBUY_CONSUMER_KEY_LIVE = config('ONBUY_CONSUMER_KEY_LIVE')

wcapi = API(
    url=WOOCOMMERCE_API_URL,
    consumer_key=WOOCOMMERCE_CONSUMER_KEY,
    consumer_secret=WOOCOMMERCE_CONSUMER_SECRET,
    version=WOOCOMMERCE_API_VERSION,
    timeout=20
)

logger = logging.getLogger(__name__)

class Syncer():
    
    __token = None
    
    def __init__(self, options) -> None:
        self.options = options
                
    def __parse_links(self, headers):
        links = headers.get("Link")
        parts = links.split(",")
            
        # Create a dictionary to store parsed links
        parsed_links = {}
        
        # Loop through each link and extract rel and URL
        for link in parts:
            url, rel = link.split(';')
            url = url.strip('</> ')
            rel = rel.split('=')[1].strip('"')
            parsed_links[rel] = url.replace(f"{WOOCOMMERCE_API_URL}/wp-json/{WOOCOMMERCE_API_VERSION}","").strip("/")
        
        # Extract next and previous links if present
        next_link = parsed_links.get('next')
        prev_link = parsed_links.get('prev')
        return prev_link, next_link

    def handle(self):
        # self.stdout.write("Hello, world!")
        logger.debug("Downloading products.")

        params = {
            'per_page' : 100,
            'page': self.options.start_page
        }
        
        response = wcapi.get("products", params=params)
        if not response.status_code==200:
            logger.warning("No products")
            return
            
        do_next = True
        page = self.options.start_page

        while do_next:
    
            logger.info(f"Processing page #{page}")
            products = response.json()
            self.__process_products(products)

            page += 1    
            prev, next = self.__parse_links(response.headers)
            logger.info("prev: {}, next: {}".format(prev,next))
            if next in [None,'']:
                do_next = False
            else:
                response = wcapi.get(next)
                logger.info(f"Downloading page #{page}")

    def __submit_to_onbuy(self,product_payload):
        pass

    def __get_onbuy_token(self):
    
        if self.__token:
            expires_at_timestamp = int(self.__token['expires_at'])
            expires_at = datetime.datetime.fromtimestamp(expires_at_timestamp)
            
            delta = expires_at - datetime.datetime.now()
            
            if delta.total_seconds() > 60:
                return self.__token
        
        url = 'https://api.onbuy.com/v2/auth/request-token'
        payload={
            'secret_key': ONBUY_SECRET_KEY_LIVE,
            'consumer_key': ONBUY_CONSUMER_KEY_LIVE
        }
        
        response = requests.request("POST", url, data=payload)
        print(response.text)
        
        self.__token = response.json()
        
        return self.__token
    
    def __find_category(self,categories):
        gender = ''
        
        cat_dict = {cat['name'].upper():cat for cat in categories}
        
        if cat_dict.get('MEN'):
            gender = 'MEN'
        
        if cat_dict.get('WOMEN'):
            gender = 'WOMEN'
        
        token = self.__get_onbuy_token()

        for c in categories:
            if c['name'].upper() in ['MEN','WOMEN']:
                continue
            
            part0 = c['name'].split("&amp;")[0].strip()
            url = "https://api.onbuy.com/v2/categories"
            params = {
                'site_id': ONBUY_SITE_ID_UK,
                'filter[can_list_in]' : '1',
                'filter[search]' : part0,
            }
            
            headers = {
                'Authorization' : token['access_token']
            }
            
            response = requests.get(url,params=params, headers=headers)
            results = response.json()['results']
            if len(results) <= 0:
                continue
            
            category = results[0]
            category_id = category.get('category_id')

            return category_id
            
    def __process_products(self, products):
        
        products_payload = []
        
        for product in products:
            
            time.sleep(2)
            
            if not product['status']=='publish':
                continue
            
            category_id = self.__find_category(product['categories'])
            if not category_id:
                continue
            
            brand_name = '' 
            default_image = ''
            
            if len(product['images'])>0:
                default_image = product['images'][0]['src']
            for a in product['attributes']:
                if 'BRAND' in a.get("name","").upper():
                    brand_name = a.get('options')[0] if a.get('options') else ''
            
            product_stock_quantity = 0
            if not product.get('stock_quantity') in [None,'']:
                product_stock_quantity = int(product.get('stock_quantity'))
                product_stock_quantity = 0 if product_stock_quantity <= 0 else product_stock_quantity
                
            product_codes = [
                f"{product['sku']}"
            ],
            listings = {
                "new" : {
                    "sku": f"{product['sku']}",
                    "price": product['price'],
                    "stock": product_stock_quantity,
                    "handling_time": 4
                }
            }
            
            product_payload = {
                'uid':str(uuid.uuid4()),
                'category_id': category_id,
                "published": "1",
                "product_name": product['name'],
                "product_codes":product_codes,
                "description": product['description'],
                "brand_name": brand_name,
                "default_image": default_image,
                "listings":listings
            }
                    
            product_id = product['id']
                        
            variations = product['variations'] 
            if len(variations) <= 0:
                products_payload.append(product_payload)
                continue
            
            logger.info(f"Downloading Variations for product #{product_id}, <{product['name']}>...")
            variants = wcapi.get(f"products/{product_id}/variations")
            for variation in variants.json():
                product_codes = [
                    f"{variation['sku']}"
                ],
                default_image = ''
                if variation.get('image'):
                    default_image = variation.get('image').get('src')
                
                options = ' - '.join([a.get('option') for a in variation['attributes'] if a.get('option')]).strip('- ')
                
                product_payload = {
                    'uid':str(uuid.uuid4()),
                    'category_id': category_id,
                    "published": "1",
                    "product_name": f"{product['name']} - {options}",
                    "product_codes":product_codes,
                    "description": product['description'],
                    "brand_name": brand_name,
                    "default_image": default_image,
                    "listings":listings
                }
                
                variant_stock_quantity = 0
                if not variation.get('stock_quantity') in [None,'']:
                    variant_stock_quantity = int(variation.get('stock_quantity'))
                    variant_stock_quantity = 0 if variant_stock_quantity <= 0 else variant_stock_quantity
                
                products_payload.append(product_payload)
        
        payload = {
            'site_id' : ONBUY_SITE_ID_UK,
            'products':products_payload    
        }
        
        # self.__submit_to_onbuy(payload)

if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--start-page",type=int,default=1)
    options = parser.parse_args()
    
    syncer = Syncer(options)
    syncer.handle()