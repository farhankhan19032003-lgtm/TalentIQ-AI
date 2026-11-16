"""interview notes (structured interview scorecards)

Revision ID: 0002
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa


revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('interview_notes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('candidate_id', sa.Integer(), nullable=False),
    sa.Column('job_id', sa.Integer(), nullable=True),
    sa.Column('round', sa.String(length=30), nullable=False),
    sa.Column('interviewer', sa.String(length=100), nullable=False),
    sa.Column('interviewed_on', sa.Date(), nullable=False),
    sa.Column('recommendation', sa.String(length=20), nullable=False),
    sa.Column('ratings', sa.JSON(), nullable=False),
    sa.Column('strengths', sa.Text(), nullable=False),
    sa.Column('concerns', sa.Text(), nullable=False),
    sa.Column('notes', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['candidate_id'], ['candidates.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('interview_notes', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_interview_notes_candidate_id'), ['candidate_id'], unique=False)


def downgrade():
    with op.batch_alter_table('interview_notes', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_interview_notes_candidate_id'))

    op.drop_table('interview_notes')
