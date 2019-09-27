{%if salt['pillar.get']('image-synchronize:in_highstate') %}
include:
    - image-synchronize/sync
{%endif %}
