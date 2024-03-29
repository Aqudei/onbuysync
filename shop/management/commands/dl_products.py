from decimal import Decimal
import time
from django.core.management.base import BaseCommand, CommandParser
from django.conf import settings
from django.forms import ValidationError
from shop.models import Product, Variation, Category
import traceback as tb
import logging 
from woocommerce import API

wcapi = API(
    url=settings.WOOCOMMERCE_API_URL,
    consumer_key=settings.WOOCOMMERCE_CONSUMER_KEY,
    consumer_secret=settings.WOOCOMMERCE_CONSUMER_SECRET,
    version=settings.WOOCOMMERCE_API_VERSION,
    timeout=20
)

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Prints "Hello, world!"'
    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--start-page",type=int, default=1)
        
        
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
            parsed_links[rel] = url.replace(f"{settings.WOOCOMMERCE_API_URL}/wp-json/{settings.WOOCOMMERCE_API_VERSION}","").strip("/")
        
        # Extract next and previous links if present
        next_link = parsed_links.get('next')
        prev_link = parsed_links.get('prev')
        return prev_link, next_link

    def handle(self, *args, **options):
        # self.stdout.write("Hello, world!")
        logger.debug("Downloading products.")

        params = {
            'per_page' : 100,
            'page': options['start_page']
        }
        

        response = wcapi.get("products", params=params)
        if not response.status_code==200:
            logger.warning("No products")
            return
            
        do_next = True
        page = options['start_page']

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

    def __process_products(self, products):
        for product in products:
            
            time.sleep(2)
            
            brand = '' 
            image = ''
            
            if len(product['images'])>0:
                image = product['images'][0]['src']
            for a in product['attributes']:
                if 'BRAND' in a.get("name","").upper():
                    brand = a.get('options')[0] if a.get('options') else ''
                    
            product_stock_quantity = 0
            if not product.get('stock_quantity') in [None,'']:
                product_stock_quantity = int(product.get('stock_quantity'))
                product_stock_quantity = 0 if product_stock_quantity <= 0 else product_stock_quantity
            
            product_id = product.pop('id')
            product_defaults = {
                'name': product['name'],
                'status': product['status'],
                'sku': product['sku'],
                'price': product.get('price') if not product.get('price','') == '' else 0.0,
                'regular_price': product.get('regular_price','') if not product.get('regular_price','') == '' else 0.0,
                'sale_price': product.get('sale_price',0.0) if not product.get('sale_price','') == '' else 0.0,
                'stock_quantity': product_stock_quantity,
                'brand':brand,
                'image':image,
                'variations_ids':', '.join("{}".format(p) for p in product.get('variations',[]))
            }

            product_obj,_ = Product.objects.update_or_create(external_id=product_id, defaults=product_defaults)
            
            cats = []
            for cat in product['categories']:
                obj, _ = Category.objects.update_or_create(name=cat['name'])
                cats.append(obj)
            
            product_obj.categories.set(cats)
            
            variations = product['variations'] 
            if len(variations) > 0:
                logger.info(f"Downloading Variations for product #{product_id}, <{product['name']}>...")
                variants = wcapi.get(f"products/{product_id}/variations")
                for variation in variants.json():
                    options = [a.get('option') for a in variation['attributes'] if a.get('option')]
                    
                    variant_stock_quantity = 0
                    if not variation.get('stock_quantity') in [None,'']:
                        variant_stock_quantity = int(variation.get('stock_quantity'))
                        variant_stock_quantity = 0 if variant_stock_quantity <= 0 else variant_stock_quantity
                        
                    variant_defaults = {
                        'name' :"{}-{}".format(product['name'], '-'.join(options) ).strip("- "),
                        'sku': variation['sku'],
                        'price': variation.get('price') if not variation.get('price','') == '' else 0.0,
                        'regular_price': variation.get('regular_price') if not variation.get('regular_price','') == '' else 0.0,
                        'sale_price': variation.get('sale_price',0.0) if not variation.get('sale_price','') == '' else 0.0,
                        'stock_quantity': variant_stock_quantity,
                        'product' : product_obj,
                        'image':variation.get('image').get('src') if variation.get('image') else ''
                    }

                    Variation.objects.update_or_create(external_id=variation['id'], defaults=variant_defaults)
