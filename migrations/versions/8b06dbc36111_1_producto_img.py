"""1 producto img

Revision ID: 8b06dbc36111
Revises: d8d19e79d0ee
Create Date: 2024-02-07 18:16:19.113760

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8b06dbc36111'
down_revision = 'd8d19e79d0ee'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('productos', schema=None) as batch_op:
        batch_op.add_column(sa.Column('ruta_imagen', sa.String(length=255), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('productos', schema=None) as batch_op:
        batch_op.drop_column('ruta_imagen')

    # ### end Alembic commands ###