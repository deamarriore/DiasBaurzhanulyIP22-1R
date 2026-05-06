from django.core.management.base import BaseCommand
from inventory.models import Category, Supplier

class Command(BaseCommand):
    help = 'Инициализирует начальные данные (категории и поставщики)'
    
    def handle(self, *args, **options):
        # Создание категорий
        categories = ['Электроника', 'Мебель', 'Канцтовары', 'Одежда', 'Инструменты']
        for cat_name in categories:
            Category.objects.get_or_create(name=cat_name)
        self.stdout.write(self.style.SUCCESS(f'✓ Создано {len(categories)} категорий'))
        
        # Создание поставщиков
        suppliers_data = [
            {
                'name': 'ООО Электросервис',
                'contact_person': 'Иван Петров',
                'phone': '+7 (495) 123-45-67',
                'email': 'info@elektroservis.ru',
                'address': 'г. Москва, Проспект Мира, д. 45, офис 120'
            },
            {
                'name': 'АО Мебельный дом',
                'contact_person': 'Мария Сидорова',
                'phone': '+7 (495) 234-56-78',
                'email': 'sales@mebeldom.ru',
                'address': 'г. Москва, Ленинградское шоссе, д. 78, стр. 2'
            },
            {
                'name': 'ООО КанцелярПро',
                'contact_person': 'Владимир Иванов',
                'phone': '+7 (495) 345-67-89',
                'email': 'support@kantselpro.ru',
                'address': 'г. Москва, ул. Новая, д. 12, литер А'
            },
            {
                'name': 'ООО ФэшнТрейд',
                'contact_person': 'Елена Морозова',
                'phone': '+7 (495) 456-78-90',
                'email': 'shop@fashiontrade.ru',
                'address': 'г. Санкт-Петербург, Невский проспект, д. 88'
            },
        ]
        
        for supplier_data in suppliers_data:
            Supplier.objects.get_or_create(**supplier_data)
        
        self.stdout.write(self.style.SUCCESS(f'✓ Создано {len(suppliers_data)} поставщиков'))
        self.stdout.write(self.style.SUCCESS('✓ Начальные данные успешно инициализированы!'))
