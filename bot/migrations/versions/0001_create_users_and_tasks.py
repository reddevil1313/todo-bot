"""create users and tasks"""
import sqlalchemy as sa
from alembic import op

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('users',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('chat_id', sa.BigInteger(), nullable=False),
    sa.Column('timezone', sa.String(length=64), nullable=False),
    sa.Column('digest_time', sa.Time(), nullable=False),
    sa.Column('alert_time', sa.Time(), nullable=False),
    sa.Column('escalate_days', sa.Integer(), nullable=False),
    sa.Column('streak', sa.Integer(), nullable=False),
    sa.Column('best_streak', sa.Integer(), nullable=False),
    sa.Column('last_completed_on', sa.Date(), nullable=True),
    sa.Column('last_digest_on', sa.Date(), nullable=True),
    sa.Column('last_alert_on', sa.Date(), nullable=True),
    sa.Column('last_review_on', sa.Date(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('tasks',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.BigInteger(), nullable=False),
    sa.Column('title', sa.String(length=300), nullable=False),
    sa.Column('due_date', sa.Date(), nullable=True),
    sa.Column('due_time', sa.Time(), nullable=True),
    sa.Column('urgent', sa.Boolean(), nullable=False),
    sa.Column('important', sa.Boolean(), nullable=False),
    sa.Column('recurrence', sa.String(length=16), nullable=True),
    sa.Column('done', sa.Boolean(), nullable=False),
    sa.Column('completed_on', sa.Date(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('tasks', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_tasks_done'), ['done'], unique=False)
        batch_op.create_index(batch_op.f('ix_tasks_user_id'), ['user_id'], unique=False)



def downgrade():
    with op.batch_alter_table('tasks', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_tasks_user_id'))
        batch_op.drop_index(batch_op.f('ix_tasks_done'))

    op.drop_table('tasks')
    op.drop_table('users')
