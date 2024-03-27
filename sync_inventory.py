import json
import logging
import requests
from decouple import config
import shopify
import time
import datetime
import csv

# Create a logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Set the logger's level

# Create a file handler
file_handler = logging.FileHandler('debug.log')
file_handler.setLevel(logging.DEBUG)  # Set the file handler's level

# Create a console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)  # Set the console handler's level

# Define the log format
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# Add handlers to the logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)

SHOPIFY_URL = config('SHOPIFY_URL')
SHOPIFY_ACCESS_TOKEN = config('SHOPIFY_ACCESS_TOKEN')
SHOPIFY_API_KEY = config('SHOPIFY_API_KEY')
SHOPIFY_API_SECRET =config('SHOPIFY_API_SECRET')
API_VERSION = '2024-01'
ONBUY_URL =	config('ONBUY_URL')
ONBUY_SELLER_ID = config('ONBUY_SELLER_ID')
ONBUY_SELLER_ENTITY_ID	= config('ONBUY_SELLER_ENTITY_ID')
ONBUY_SITE_ID_UK = config('ONBUY_SITE_ID_UK')

ONBUY_CONSUMER_KEY_LIVE =	config('ONBUY_CONSUMER_KEY_LIVE')
ONBUY_SECRET_KEY_LIVE =	config('ONBUY_SECRET_KEY_LIVE')

ONBUY_CONSUMER_KEY_TEST =	config('ONBUY_CONSUMER_KEY_TEST')
ONBUY_SECRET_KEY_TEST =	config('ONBUY_SECRET_KEY_TEST')
LOCATION_ID = config('LOCATION_ID')



def dl_inventory_locs():

    with shopify.Session.temp(SHOPIFY_URL, API_VERSION, SHOPIFY_ACCESS_TOKEN):
        loc_list = []
        locations = shopify.Location.find()
        
        has_next_page = True
        while has_next_page:
            for loc in locations:
                loc_list.append(loc.to_dict())
            
            has_next_page = locations.has_next_page()
            if has_next_page:
                locations = locations.next_page()
            
        with open("./data/locations.json",'wt') as outfile:
            outfile.write(json.dumps(loc_list,indent=4))

def dl_inventory():
    levels_list = []
    with shopify.Session.temp(SHOPIFY_URL, API_VERSION, SHOPIFY_ACCESS_TOKEN):
        inventory_levels = shopify.InventoryLevel.find(location_ids=LOCATION_ID)
        
        do_next = True
        
        while do_next:
            for level in inventory_levels:
                levels_list.append(level.to_dict())
            
            do_next = inventory_levels.has_next_page()
            if do_next:
                inventory_levels=inventory_levels.next_page()
                
        with open("./data/inventory_levels.json",'wt') as outfile:
            outfile.write(json.dumps(levels_list,indent=4))

def get_onbuy_token():
    
    url = 'https://api.onbuy.com/v2/auth/request-token'
    
    payload=json.dumps({
        'secret_key': ONBUY_SECRET_KEY_LIVE,
        'consumer_key': ONBUY_CONSUMER_KEY_LIVE
    })
    
    # url = "https://api.onbuy.com/v2auth/request-token"

    payload = {
        'secret_key': ONBUY_SECRET_KEY_LIVE,
        'consumer_key': ONBUY_CONSUMER_KEY_LIVE
        }
    files=[

    ]
    headers = {

    }

    
    response = requests.request("POST", url, headers=headers, data=payload, files=files)
    print(response.text)
    
    while response.status_code==504:
        response = requests.request("POST", url, headers=headers, data=payload, files=files)
        print(response.text)
        time.sleep(1)
    
    return response.json()

def upload_listings(filename):

    token = get_onbuy_token()

    payload  = {
        'site_id' : ONBUY_SITE_ID_UK,
        'listings' : listings
    }
    
    delta = datetime.datetime.fromtimestamp(int(token['expires_at']))  - datetime.datetime.now()
    if delta.total_seconds() <  (5 * 60):
        token = get_onbuy_token()
        
    headers = {
        'Authorization': f"{token['access_token']}",
        'Content-Type': 'application/json'
    }
    
    import pdb; pdb.set_trace()
    payload_json = json.dumps(payload)
    response = requests.put('https://api.onbuy.com/v2/listings/by-sku',headers=headers,data=payload_json)
    
    logger.debug("Response:")
    logger.debug(response.text)
    
def dl_listings():
    token = get_onbuy_token()
    
    url = "https://api.onbuy.com/v2/listings"
    
    limit = 50
    offset = 0
    
    params = {
        'site_id':ONBUY_SITE_ID_UK,
        'sort[last_created]':'asc',
        'site_id':ONBUY_SITE_ID_UK,
        'limit' : limit,
        'offset'  : offset
    }
    payload={}
    headers = {
        'Authorization': token['access_token']
    }

    do_next = True
    
    with open("./data/listings.csv",'wt', newline='') as outfile:
        writer=csv.writer(outfile)
        writer.writerow(('name','sku','price','stock'))
        
        while do_next:
            logger.info(f"@dl_listings, limit: {params['limit']}, offset: {params['offset']}")
            response = requests.request("GET", url, headers=headers, data=payload, params=params)
            if not response.status_code==200:
                logger.error(response.text)
                break
            
            results = response.json().get('results',[])
            if len(results) <= 0:
                break
        
        
            for item in results:
                writer.writerow((item['name'],item['sku'],item['price'],item['stock']))
            
            if len(results) < params['limit']:
                break
            
            params.update({
                'offset' :params['offset'] + params['limit']
            }) 
            

def update_prices():
    with open('./data/listings.csv','rt') as infile:
        with shopify.Session.temp(SHOPIFY_URL, API_VERSION, SHOPIFY_ACCESS_TOKEN):
            graphql = shopify.GraphQL()
            reader = csv.DictReader(infile)
            listings = []
            for item in reader:
                query = '''query {
                    productVariants(first: 1,query:"sku:'%s'") {
                        edges {
                            node {
                                sku
                                price
                                inventoryItem {
                                    id
                                    available
                                }
                            }
                        }
                    }
                }''' % (item['sku'])
                
                graphql_response = json.loads(graphql.execute(query))
                variants = graphql_response.get('data',{}).get('productVariants',{}).get('edges',[])
                if len(variants)<=0:
                    continue
                
                import pdb; pdb.set_trace()

                inventory_item = shopify.InventoryItem.find(variants[0].inventory_item_id)

                listings.append(
                    {
                        'sku':variants[0]['sku'],
                        'price':variants[0]['price'],
                        'stock':inventory_item.level
                    }
                )
                
    
        

def pre_inventory():
    with shopify.Session.temp(SHOPIFY_URL, API_VERSION, SHOPIFY_ACCESS_TOKEN):
        graphql = shopify.GraphQL()
        inventory_levels = shopify.InventoryLevel.find(location_ids=LOCATION_ID)
        
        do_next = True
        with open('./data/listings.csv','wt',newline='') as outfile:
            writer = csv.writer(outfile)
            writer.writerow(('sku','price','stock'))
            rows_count = 0
            while do_next:
                for level in inventory_levels:
                    inventory_item = shopify.InventoryItem.find(level.inventory_item_id)
                    time.sleep(2)
                    if not inventory_item:
                        continue
                    if  inventory_item.sku in ['',None]:
                        continue
                    
                    query = '''query {
                        productVariants(first: 1,query:"sku:'%s'") {
                            edges {
                                node {
                                    sku
                                    price
                                }
                            }
                        }
                    }''' % (inventory_item.sku,)
                    
                    graphql_response = json.loads(graphql.execute(query))

                    variants = graphql_response.get('data',{}).get('productVariants',{}).get('edges',[])
                    time.sleep(2)
                    if len(variants)<=0:
                        continue
                    
                    writer.writerow((inventory_item.sku,variants[0]['node']['price'],level.available))
                    rows_count += 1
                    
                do_next = inventory_levels.has_next_page()
                time.sleep(2)
                if do_next:
                    inventory_levels=inventory_levels.next_page()
                    time.sleep(2)
                
            
            logger.info(f"Total listing item: {rows_count}")
            
            
if __name__ == "__main__":    
    # dl_listings()
    update_prices()