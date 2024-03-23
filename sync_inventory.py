import json
import logging
import requests
from decouple import config
import shopify

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

ONBUY_URL =	config('ONBUY_URL')
ONBUY_SELLER_ID = config('ONBUY_SELLER_ID')
ONBUY_SELLER_ENTITY_ID	= config('ONBUY_SELLER_ENTITY_ID')
ONBUY_SITE_ID_UK = config('ONBUY_SITE_ID_UK')

ONBUY_CONSUMER_KEY_LIVE =	config('ONBUY_CONSUMER_KEY_LIVE')
ONBUY_SECRET_KEY_LIVE =	config('ONBUY_SECRET_KEY_LIVE')

ONBUY_CONSUMER_KEY_TEST =	config('ONBUY_CONSUMER_KEY_TEST')
ONBUY_SECRET_KEY_TEST =	config('ONBUY_SECRET_KEY_TEST')
LOCATION_ID = config('LOCATION_ID')

API_VERSION = '2024-01'

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
    
    # payload={
    #     'secret_key': ONBUY_SECRET_KEY_TEST,
    #     'consumer_key': ONBUY_CONSUMER_KEY_TEST
    # }
        
    headers = {
        'Content-Type': 'application/json'
    }
    response = requests.post(url,json=payload,headers=headers,stream=False)
    logger.debug("Response:")
    logger.debug(response.content)
    import pdb; pdb.set_trace()
    if response.status_code==200:
        return response.json()
        
def sync_inventory():


    with shopify.Session.temp(SHOPIFY_URL, API_VERSION, SHOPIFY_ACCESS_TOKEN):
        inventory_levels = shopify.InventoryLevel.find(location_ids=LOCATION_ID)
        
        do_next = True
        
        while do_next:
            listings = []
            for level in inventory_levels:
                inventory_item = shopify.InventoryItem.find(level.inventory_item_id)
                if not inventory_item:
                    continue
                
                cost = inventory_item.cost
                    
                listings.append({
                    'sku':inventory_item.sku,
                    'price':inventory_item.cost,
                    'stock':level.available
                })
            
            payload  = {
                'site_id' : ONBUY_SITE_ID_UK,
                'listings' : listings
            }
            
            headers = {
                'Authorization': '4E7DREERR2189-A943-4697-C295-fCA434558518',
                'Content-Type': 'application/json'
            }
            
            payload_json = json.dumps(payload)
            response = requests.post('https://api.onbuy.com/v2/listings/by-sku',headers=headers,data=payload_json)
            
            logger.debug("Response:")
            logger.debug(response.text)
            
            do_next = inventory_levels.has_next_page()
            if do_next:
                inventory_levels=inventory_levels.next_page()
            
            
if __name__ == "__main__":    
    token = get_onbuy_token()
