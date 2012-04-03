Prerequisites:

See the fabric documentation at: http://docs.fabfile.org

Install fabric:

```bash
$ sudo pip install fabric
```


Getting started:

This currently only works when SSH is enabled on the target machine (even if it is localhost)

Install fabric as per: http://docs.fabfile.org/en/1.3.4/index.html#installation

Command examples:
<pre>
  install:
    install(aegir_version='', hostname = ''):
      eg.
      fab -H localhost install
      #           \
      #            this is the host you wish to SSH into for install

      fab -H localhost install:aegir_version='6.x-1.6'
      fab -H localhost install:hostname='myaegir.ld'
      fab -H localhost install:aegir_version='6.x-1.6',hostname='myaegir.ld'
</pre>
