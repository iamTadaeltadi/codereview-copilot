import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_thread_created_by'),
    ]

    operations = [
        migrations.AddField(
            model_name='review',
            name='condition',
            field=models.CharField(blank=True, db_index=True, max_length=20, null=True),
        ),
        migrations.AlterField(
            model_name='review',
            name='status',
            field=models.CharField(
                choices=[
                    ('pending', 'Pending'),
                    ('in_progress', 'In Progress'),
                    ('completed', 'Completed'),
                    ('failed', 'Failed'),
                    ('processing', 'Processing'),
                    ('pending_analysis', 'Pending Analysis'),
                ],
                db_index=True,
                default='pending',
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name='review',
            name='parent_review',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='re_reviews',
                to='core.review',
            ),
        ),
        migrations.AddField(
            model_name='llmusage',
            name='step',
            field=models.CharField(blank=True, db_index=True, max_length=50, null=True),
        ),
        migrations.AddConstraint(
            model_name='reviewfeedback',
            constraint=models.CheckConstraint(
                condition=models.Q(('rating__gte', 1), ('rating__lte', 5)),
                name='check_rating_range',
            ),
        ),
        migrations.CreateModel(
            name='Finding',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('file_path', models.CharField(blank=True, max_length=500)),
                ('line', models.IntegerField(blank=True, null=True)),
                ('severity', models.CharField(blank=True, db_index=True, max_length=20)),
                ('kind', models.CharField(blank=True, db_index=True, max_length=50)),
                ('message', models.TextField(blank=True)),
                ('raw', models.JSONField()),
                ('review', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='findings',
                    to='core.review',
                )),
            ],
            options={'abstract': False},
        ),
    ]
