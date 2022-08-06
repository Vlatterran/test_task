import dateutil.parser
import tortoise.fields as fields
from tortoise import Model, Tortoise


class Order(Model):
    number = fields.IntField(pk=True, generated=False, description='заказ №')
    cost_usd = fields.DecimalField(null=False, description='стоимость,$', decimal_places=2, max_digits=10)
    cost_rub = fields.DecimalField(null=False, description='стоимость,₽', decimal_places=2, max_digits=10)
    delivery_date = fields.DateField(null=False, description='срок поставки')

    @classmethod
    def from_googlesheet_line(cls, line, usd_cost):
        try:
            return cls(number=line[1],
                       cost_usd=(cost := float(line[2])),
                       cost_rub=cost * usd_cost,
                       delivery_date=dateutil.parser.parse(line[3]).date())
        except IndexError:
            return


async def init_db(db_url: str):
    await Tortoise.init(
        db_url=db_url,
        modules={'models': ['models']}
    )
    await Tortoise.generate_schemas()
