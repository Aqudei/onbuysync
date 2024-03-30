from django.core.management.base import BaseCommand, CommandParser
from shop.models import Product,Variation,Category
import requests
import json
from django.conf import settings

class Command(BaseCommand):
    
    def __get_onbuy_token(self):
    
        url = 'https://api.onbuy.com/v2/auth/request-token'
        payload={
            'secret_key': settings.ONBUY_SECRET_KEY_LIVE,
            'consumer_key': settings.ONBUY_CONSUMER_KEY_LIVE
        }
        
        response = requests.request("POST", url, data=payload)
        print(response.text)
        
        return response.json()
    
    def __find_category(self,search):
        
        params = {
            'site_id' : settings.ONBUY_SITE_ID_UK,
            'filter[can_list_in]' : 1,
            'filter[search]' : search,
            
        }
        url ="https://api.onbuy.com/v2/categories"
        token = self.__get_onbuy_token()
        headers = {
            'Authorization' : token['access_token']
        }
        response = requests.get(url,headers=headers,params=params)
        return response.json()
    
    def handle(self, *args, **options):
        products = Product.objects.filter(status='publish').exclude(brand='').exclude(brand=None)
        for product in products:
            url = "https://api.onbuy.com/v2/products"
            category_name = product.categories.first().name.split("&amp;")[0]
            category = self.__find_category(category_name)
            import pdb; pdb.set_trace()
        
            payload = json.dumps({
                "site_id": settings.ONBUY_SITE_ID_UK,
                "category_id": category.get('results',[])[0].get('category_id'),
                "live": "1",
                "brand_name": product.brand,
                "product_name": product.name,
                "description": "Comfortable fit, easy release.",
                "default_image": "http://www.freepngimg.com/download/lion/3-2-lion-png.png",
                "additional_images": [
                    "http://c1.staticflickr.com/9/8381/8613405336_11caf04e28_b.jpg"
                ],
                "variant_1": {
                    "feature_id": 102
                },
                "variants": [
                    {
                    "variant_1": {
                        "option_id": 620
                    },
                    "default_image": "http://west-moors.co.uk/images/red.png",
                    "rrp": "499.99",
                    "product_codes": [
                        "5034982266920"
                    ],
                    "features": [
                        {
                        "option_id": 93,
                        "name": "slime green"
                        }
                    ],
                    "listings": {
                        "new": {
                        "sku": "v99-5076371426621-NEW",
                        "price": 449.99,
                        "stock": 3
                        }
                    }
                    },
                    {
                    "variant_1": {
                        "option_id": 621
                    },
                    "default_image": "http://west-moors.co.uk/images/blue.png",
                    "rrp": "499.99",
                    "product_codes": [
                        "5011232442754"
                    ],
                    "listings": {
                        "new": {
                        "sku": "v99-51080-7B-NEW",
                        "price": 449.99,
                        "stock": 3
                        }
                    },
                    "features": [
                        {
                        "option_id": 93,
                        "name": "puke green",
                        "hex": "#A3C00F"
                        }
                    ],
                    "product_data": [
                        {
                        "label": "label1",
                        "value": "value1"
                        },
                        {
                        "label": "label2",
                        "value": "value2"
                        }
                    ]
                    },
                    {
                    "variant_1": {
                        "option_id": 622
                    },
                    "default_image": "http://west-moors.co.uk/images/green.png",
                    "rrp": "499.99",
                    "product_codes": [
                        "5031459073043"
                    ],
                    "features": [
                        {
                        "option_id": 93,
                        "name": "putting green"
                        }
                    ],
                    "listings": {
                        "new": {
                        "sku": "v3-94462-7B-NEW",
                        "price": 449.99,
                        "stock": 3
                        }
                    },
                    "product_data": [
                        {
                        "label": "label1",
                        "value": "value1"
                        },
                        {
                        "label": "label2",
                        "value": "value2"
                        }
                    ]
                    }
                ]
            })
            headers = {
            'Authorization': '4E7DREERR2189-A943-4697-C295-fCA434558518',
            'Content-Type': 'application/json'
            }

            response = requests.request("POST", url, headers=headers, data=payload)

            print(response.text)
