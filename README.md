This currently only works when SSH is enabled on the target machine (even if it is localhost)

Command examples:
<pre>
  install:
    install(aegir_version='', hostname = '', type='beginning'):
      fab -H localhost install
      #           \
      #            this is the host you wish to SSH into for install

      # and after restart:
      fab -H localhost install:aegir_version='6.x-1.6',type='end'
      fab -H localhost install:hostname='myaegir.ld',type='end'
      fab -H localhost install:type='end'
</pre>
