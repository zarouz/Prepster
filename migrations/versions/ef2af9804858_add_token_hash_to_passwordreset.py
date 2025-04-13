"""Add token_hash to PasswordReset

Revision ID: ef2af9804858
Revises: 
Create Date: 2025-04-13 13:17:55.053875

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'ef2af9804858'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('password_reset', schema=None) as batch_op:
        batch_op.add_column(sa.Column('token_hash', sa.String(length=128), nullable=False))
        batch_op.add_column(sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=False))
        batch_op.add_column(sa.Column('expires_at', sa.TIMESTAMP(), nullable=False))
        batch_op.alter_column('user_id',
               existing_type=sa.INTEGER(),
               nullable=False)
        batch_op.create_index(batch_op.f('ix_password_reset_user_id'), ['user_id'], unique=False)
        batch_op.create_unique_constraint(None, ['token_hash'])
        batch_op.drop_column('reset_token')

    with op.batch_alter_table('reports', schema=None) as batch_op:
        batch_op.alter_column('user_id',
               existing_type=sa.INTEGER(),
               nullable=False)
        batch_op.alter_column('created_at',
               existing_type=postgresql.TIMESTAMP(),
               nullable=False,
               existing_server_default=sa.text('CURRENT_TIMESTAMP'))
        batch_op.create_index(batch_op.f('ix_reports_user_id'), ['user_id'], unique=False)

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('failed_attempts',
               existing_type=sa.INTEGER(),
               nullable=False,
               existing_server_default=sa.text('0'))
        batch_op.alter_column('is_locked',
               existing_type=sa.BOOLEAN(),
               nullable=False,
               existing_server_default=sa.text('false'))
        batch_op.alter_column('created_at',
               existing_type=postgresql.TIMESTAMP(),
               nullable=False,
               existing_server_default=sa.text('CURRENT_TIMESTAMP'))
        batch_op.alter_column('updated_at',
               existing_type=postgresql.TIMESTAMP(),
               nullable=False,
               existing_server_default=sa.text('CURRENT_TIMESTAMP'))
        batch_op.drop_constraint('users_email_key', type_='unique')
        batch_op.create_index(batch_op.f('ix_users_email'), ['email'], unique=True)

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_users_email'))
        batch_op.create_unique_constraint('users_email_key', ['email'])
        batch_op.alter_column('updated_at',
               existing_type=postgresql.TIMESTAMP(),
               nullable=True,
               existing_server_default=sa.text('CURRENT_TIMESTAMP'))
        batch_op.alter_column('created_at',
               existing_type=postgresql.TIMESTAMP(),
               nullable=True,
               existing_server_default=sa.text('CURRENT_TIMESTAMP'))
        batch_op.alter_column('is_locked',
               existing_type=sa.BOOLEAN(),
               nullable=True,
               existing_server_default=sa.text('false'))
        batch_op.alter_column('failed_attempts',
               existing_type=sa.INTEGER(),
               nullable=True,
               existing_server_default=sa.text('0'))

    with op.batch_alter_table('reports', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_reports_user_id'))
        batch_op.alter_column('created_at',
               existing_type=postgresql.TIMESTAMP(),
               nullable=True,
               existing_server_default=sa.text('CURRENT_TIMESTAMP'))
        batch_op.alter_column('user_id',
               existing_type=sa.INTEGER(),
               nullable=True)

    with op.batch_alter_table('password_reset', schema=None) as batch_op:
        batch_op.add_column(sa.Column('reset_token', sa.TEXT(), autoincrement=False, nullable=False))
        batch_op.drop_constraint(None, type_='unique')
        batch_op.drop_index(batch_op.f('ix_password_reset_user_id'))
        batch_op.alter_column('user_id',
               existing_type=sa.INTEGER(),
               nullable=True)
        batch_op.drop_column('expires_at')
        batch_op.drop_column('created_at')
        batch_op.drop_column('token_hash')

    # ### end Alembic commands ###
