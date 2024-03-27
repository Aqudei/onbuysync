import shopify
from decouple import config
import json

SHOPIFY_URL = config('SHOPIFY_URL')
SHOPIFY_ACCESS_TOKEN = config('SHOPIFY_ACCESS_TOKEN')
SHOPIFY_API_KEY = config('SHOPIFY_API_KEY')
SHOPIFY_API_SECRET =config('SHOPIFY_API_SECRET')
API_VERSION = '2024-01'
LOCATION_ID = config('LOCATION_ID')

with shopify.Session.temp(SHOPIFY_URL, API_VERSION, SHOPIFY_ACCESS_TOKEN):
    graphql = shopify.GraphQL()
    gid = 'gid://shopify/Location/{}'.format(LOCATION_ID)
    query = '''query {
        productVariants(first: 1) {
            edges {
                node {
                    sku
                    price
                    inventoryItem {
                        inventoryLevel(locationId: "%s") 
                        { 
                            available
                        }
                    }
                }
            }
        }
    }''' % (gid ,)
        
    graphql_response = json.loads(graphql.execute(query))
    import pdb; pdb.set_trace()