import shopify
from decouple import config


SHOPIFY_URL = config('SHOPIFY_URL')
SHOPIFY_ACCESS_TOKEN = config('SHOPIFY_ACCESS_TOKEN')
SHOPIFY_API_KEY = config('SHOPIFY_API_KEY')
SHOPIFY_API_SECRET =config('SHOPIFY_API_SECRET')
API_VERSION = '2024-01'

with shopify.Session.temp(SHOPIFY_URL, API_VERSION, SHOPIFY_ACCESS_TOKEN):
    # variant = shopify.Variant.find({'sku':'bts-8470001620835'})
    query = '''query {
        productVariants(first: 1,query:"sku:'bts-729001152104222'") {
            edges {
            node {
                id, sku
            }
            }
        }
    }'''
    client = shopify.GraphQL()
    
    response = client.execute(query)
    import pdb; pdb.set_trace()