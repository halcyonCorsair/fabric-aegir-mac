Command examples:
<pre>
  install:
    install(aegir_version='', hostname = '', type='beginning'):
      fab -H localhost install
      # and after restart:
      fab -H localhost install:aegir_version='6.x-1.6',type='end'
      fab -H localhost install:hostname='myaegir.ld',type='end'
      fab -H localhost install:type='end'
</pre>