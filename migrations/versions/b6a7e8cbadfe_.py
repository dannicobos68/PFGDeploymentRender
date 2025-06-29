"""empty message

Revision ID: b6a7e8cbadfe
Revises: c01fede9b171
Create Date: 2025-06-19 21:00:35.413368

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b6a7e8cbadfe'
down_revision = 'c01fede9b171'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('user',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('email', sa.String(length=100), nullable=False),
    sa.Column('username', sa.String(length=100), nullable=False),
    sa.Column('password', sa.String(length=200), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email'),
    sa.UniqueConstraint('username')
    )
    op.create_table('videos',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('titulo', sa.String(length=100), nullable=False),
    sa.Column('url', sa.String(length=1000), nullable=False),
    sa.Column('rating', sa.Integer(), nullable=True),
    sa.Column('idUsuario', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['idUsuario'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('infoVideo',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('texto', sa.Text(), nullable=False),
    sa.Column('embedding', sa.Text(), nullable=False),
    sa.Column('idVideo', sa.Integer(), nullable=False),
    sa.Column('idUsuario', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['idUsuario'], ['user.id'], ),
    sa.ForeignKeyConstraint(['idVideo'], ['videos.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('llamada',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('pregunta', sa.String(length=10000), nullable=False),
    sa.Column('respuesta', sa.Text(), nullable=False),
    sa.Column('fecha', sa.DateTime(), nullable=False),
    sa.Column('idUsuario', sa.Integer(), nullable=False),
    sa.Column('idVideo', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['idUsuario'], ['user.id'], ),
    sa.ForeignKeyConstraint(['idVideo'], ['videos.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('llamada')
    op.drop_table('infoVideo')
    op.drop_table('videos')
    op.drop_table('user')
    # ### end Alembic commands ###
