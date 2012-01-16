Command examples:
  install:
    install(aegir_version, php_version, hostname = '', type='beginning'):
      fab install:'6.x-1.6','5.2.8'
      fab install:'6.x-1.6','5.2.8','myaegir.ld'
      fab install:'6.x-1.6','5.2.8','myaegir.ld',type='end'
