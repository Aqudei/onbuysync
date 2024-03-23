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
console_handler.setLevel(logging.INFO)  # Set the console handler's level

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
            
        with open("./locations.json",'wt') as outfile:
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
                
        with open("./inventory_levels.json",'wt') as outfile:
            outfile.write(json.dumps(levels_list,indent=4))
if __name__ == "__main__":    
    dl_inventory()