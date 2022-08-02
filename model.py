from tortoise import Model, Tortoise, run_async
import tortoise.fields as fields


class Order(Model):
    number = fields.IntField(pk=True, generated=False, description='заказ №')
    cost_usd = fields.IntField(null=False, description='стоимость,$')
    cost_rub = fields.IntField(null=False, description='стоимость,₽')
    delivery_date = fields.DateField(null=False, description='срок поставки')


async def init():
    # Here we create a SQLite DB using file "db.sqlite3"
    #  also specify the app name of "models"
    #  which contain models from "app.models"
    await Tortoise.init(
        db_url='postgres://python@127.0.0.1:5432/mydb',
        modules={'models': ['model']}
    )


if __name__ == '__main__':
    run_async(init())
    run_async(Tortoise.generate_schemas())
