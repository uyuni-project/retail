

{%- set partitioning = salt['pillar.get']('partitioning', {}) %}
{%- set images = salt['pillar.get']('images', {}) %}

# cache all images in use
{% for disk_id, disk_data in partitioning.items() %}
# iterate over partitions or fall back to whole disk if no partitions exists
{% set todo_data = disk_data.get('partitions') %}
{% if disk_data.get('disklabel') == 'none': %}
{%   set todo_data = { '' : disk_data } %}
{% endif %}
{% for part_id, part_data in todo_data.items() %}
{% if 'image' in part_data %}
image_for_{{ disk_id + part_id }}_downloaded:
  saltboot.image_downloaded:
    - name: {{ disk_id + part_id }}
    - partitioning: {{ partitioning|yaml }}
    - images: {{ images|yaml }}

{% endif %}
{% endfor %}
{% endfor %}

