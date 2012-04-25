from fabric.api import *
from fabric.colors import green, red, yellow
from fabric.contrib.console import confirm
from fabric.contrib.files import *
import random, re, string, sys, time

time = time.strftime('%Y%m%d-%H%M')

# NOTE: fabric bug: osx uses -E instead of -r, this means sed(), comment(), and uncomment() won't work properly
# TODO: perl inline replacement: perl -p -i.bak -e "s#a#b#" filename

def install(aegir_version='', hostname=''):
  env.arguments = "%s, hostname = '%s'" % (aegir_version, hostname)
  env.hostname = hostname

  check_requirements()
  #NOTE: uncomment check_testing() and comment out setup_apps() to skip mariadb nginx and php, or the reverse to install for real
  #check_testing()
  setup_apps()
  set_hostname()
  install_drush()
  install_aegir()

def check_requirements():
  check_xcode()
  check_homebrew()

def ping(host):
  run('ping -c 3 %s' % host)

def check_xcode():
  print(green('>>> Install the requirements for this process; Xcode'))

  print(green('>>>> XCode is required for Homebrew to compile nginx, mariadb and php.'))
  print(green('>>>> Download and install Xcode using the Mac App Store with the link above'))
  print(green(">>>> (it's free, but will take a while to download if your Internet connection is slow)"))
  print(green('>>>> Once the download has finished run the newly downloaded "Install Xcode" app which will appear in Launchpad and follow the prompts.'))
  if (not confirm('Is XCode installed?', default=False)):
    abort('XCode is required by Homebrew')

def check_homebrew():
  print(green('>>> Install the requirements for this process; Homebrew'))

  if (not confirm('Is homebrew installed?', default=False)):
    install_homebrew()

def check_testing():
print(green('>>> Installable components; MariaDB'))

  if (not confirm('Are you testing aegir parts?', default=False)):
    setup_apps()

def setup_apps():
  check_mariadb()
  check_nginx()
  check_php()

def check_mariadb():
  print(green('>>> Installable components; MariaDB'))

  if (not confirm('Is mariadb already installed?', default=False)):
    install_mariadb()

def check_nginx():
  print(green('>>> Installable components; nginx'))

  if (not confirm('Is nginx already installed?', default=False)):
    install_nginx()

def check_php():
  print(green('>>> Installable components; php'))

  if (not confirm('Is php already installed?', default=False)):
    update_php()

def install_homebrew():
  print(green('>>> Install Homebrew'))
  run('/usr/bin/ruby -e "$(/usr/bin/curl -fksSL https://raw.github.com/mxcl/homebrew/master/Library/Contributions/install_homebrew.rb)"')
  run('mkdir -p /usr/local/Cellar')
  with settings(warn_only=True):
    run('brew doctor')

  print(green('>>>> Add /usr/local/sbin to your path'))
  path_update = 'PATH=$PATH:/usr/local/sbin; export PATH'
  username = run('whoami')
  with settings(warn_only=True):
    if run("test -f /Users/%s/.bash_profile" % username).failed:
      run('echo "%s" > /Users/%s/.bash_profile' % (path_update, username))
    elif (not contains('/Users/%s/.bash_profile' % username, 'sbin; export PATH')):
      append("/Users/%s/.bash_profile" % username, path_update, use_sudo=False)

def homebrew_add_tap(tap=''):
  print(yellow('>>>> Setup homebrew tap for %s' % tap))
  with settings(warn_only=True):
    run('brew tap %s' % tap)

def update_hosts(domain='', ip='127.0.0.1'):
  hosts = '/etc/hosts'
  if (domain == ''):
    domain = run('hostname -f')
  if (domain != 'localhost' and contains(hosts, domain)):
    sudo("sed -i.bak -E -e 's/(.*%s)/#\\1/g' /etc/hosts" % domain)
  sudo('echo "%s  %s" >> /etc/hosts' % (ip, domain))

def set_hostname(hostname=''):
  print(green(">>>> Current Hostname:"))
  current_hostname = run('hostname -f')

  print(green(">>>> Set hostname as it's required for sane default in aegir setup, for example 'test.ld'.  You can use something else instead of test, but it needs to end in .ld"))

  if (hostname != ''):
    env.hostname = hostname
  elif confirm('Your current hostname is %s, do you want to change your hostname?' % current_hostname, default=False):
    env.hostname = prompt('Please enter your desired hostname:', key=None, default=current_hostname, validate=None)
    if (env.hostname == ''):
      abort('You have entered an incorrect hostname')
  else:
    return

  sudo('scutil --set HostName %s' % env.hostname)
  update_hosts()

def setup_named():
  #Backup the default configuration
  with settings(warn_only=True):
    if run("test -f /etc/named.conf.bck").failed:
      sudo('cp /etc/named.conf /etc/named.conf.bck')

  #Create the keyfile that is read by both rndc and named on startup
  sudo('rndc-confgen -a')

  #Edit the named.conf file
  #Inside the "options {" block add the following before the last }
  #forwarders {
  #       8.8.8.8;  //Google DNS
  #       8.8.4.4;  //Google DNS
  #};
  sudo('perl -p -i.bak -e "s/options {\n/options {\n        forwarders {\n          8.8.8.8; \/\/ Google DNS\n          8.8.4.4; \/\/ Google DNS\n        };\n/" /etc/named.conf')

  #Add the following just before zone "0.0.127.in-addr.arpa" IN {
  #zone "ld" IN {
  #       type master;
  #       file "db.ld";
  #};
  sudo('perl -p -i.bak -e \'s/(zone "0.0.127.in-addr.arpa" IN {)/zone "ld" IN {\n        type master;\n        file "db.ld";\n};\n\n\\1/\' /etc/named.conf')

  # Put our db.ld file in place
  with settings(warn_only=True):
    if run("test -f /var/named/db.ld").failed:
      put('db.ld', '/var/named/db.ld', use_sudo=True)

  #Run the following commands to ensure configuration is ok
  sudo('named-checkconf /etc/named.conf')
  sudo('named-checkzone ld /var/named/db.ld')

  #Create configuration so that the wilcard is still accesible when you are not connected to a network
  sudo('mkdir -p /etc/resolver')
  sudo('echo "nameserver 127.0.0.1" >> /etc/resolver/ld')

  #Set Bind to load on startup, and load it right now
  with settings(warn_only=True):
    sudo('launchctl unload -w /System/Library/LaunchDaemons/org.isc.named.plist')
  sudo('launchctl load -w /System/Library/LaunchDaemons/org.isc.named.plist')

  #Check setup with dig, were looking for NOERROR in the returned text
  run('dig test.ld')

  print(yellow('>>>> Set your computers network settings to use 127.0.0.1 as DNS server in System Preferences -> Network for both Wireless and Ethernet connections by clicking Advanced and selecting the DNS tab'))
  if (confirm('Have you set 127.0.0.1 as your DNS server?', default=False)):
    #test via ping (if it fails, try a restart or dscacheutil -flushcache)
    ping('test.ld')

def install_mariadb(mariadb_version=''):
  print(green('>>> Install MariaDB'))
  print(green('>>>> MariaDB is a community-developed branch of the MySQL database, the impetus being the community maintenance of its free status under GPL, as opposed to any uncertainty of MySQL license status under its current ownership by Oracle.'))
  print(green('>>>> The intent also being to maintain high fidelity with MySQL, ensuring a "drop-in" replacement capability with library binary equivalency and exacting matching with MySQL APIs and commands. It includes the XtraDB storage engine as a replacement for InnoDB.'))

  run('brew install mariadb')

  if (mariadb_version == ''):
    mariadb_version = run("brew info mariadb 2> /dev/null | grep ^mariadb | sed 's/mariadb //g'")

  print(green('>>>> Once compilation has finished unset TMPDIR'))
  print(green('>>>> Then mysql_install_db'))
  run('unset TMPDIR && mysql_install_db')

  print(green('>>> Answer the prompts as follows, replace [password] with a password of your own chosing'))
  print(yellow('>>>> Enter current password for root (enter for none): [Enter]'))
  print(yellow('>>>> Set root password? [Y/n] y'))
  print(yellow('>>>> New password: [password]'))
  print(yellow('>>>> Re-enter new password: [password]'))
  print(yellow('>>>> Remove anonymous users? [Y/n] y'))
  print(yellow('>>>> Disallow root login remotely? [Y/n] y'))
  print(yellow('>>>> Remove test database and access to it? [Y/n] y'))
  print(yellow('>>>> Reload privilege tables now? [Y/n] y'))
  print('')
  run('mysql.server start')
  run('unset TMPDIR && /usr/local/Cellar/mariadb/%s/bin/mysql_secure_installation' % mariadb_version)

  print(green('>>>> Copy the LaunchDaemon to load mariadb on boot into place'))
  sudo('cp /usr/local/Cellar/mariadb/%s/homebrew.mxcl.mariadb.plist /System/Library/LaunchDaemons/homebrew.mxcl.mariadb.plist' % mariadb_version)
  sudo('launchctl load -w /System/Library/LaunchDaemons/homebrew.mxcl.mariadb.plist')

def install_nginx():
  print(green('>>> Setting up Nginx'))
  print(green('>>>> Prevent apache from being loaded automatically'))
  sudo('launchctl unload -w /System/Library/LaunchDaemons/org.apache.httpd.plist')

  print(green('>>>> Modify homebrew recipe to add debugging'))
  nginx_recipe = '/usr/local/Library/Formula/nginx.rb'
  if (not contains(nginx_recipe, '--with-debug')):
    run('perl -p -i.bak -e \'s/(args = \["--prefix=#{prefix}",)/\\1\n            "--with-debug",/g\' %s' % nginx_recipe)

  run('brew install nginx')

  print(green('>>>> Make nginx log files visible in Console app'))
  sudo('mkdir /var/log/nginx')

  print(green('>>>> Create the following directory to stop "/var/lib/nginx/speed" failed (2: No such file or directory) error'))
  sudo('mkdir /var/lib/nginx')

  print(green('>>>> Allow your user to restart nginx.'))
  username = run('whoami')
  sudo('echo "%s ALL=NOPASSWD: /usr/local/sbin/nginx" >> /etc/sudoers' % username)

  print(yellow(">>>> NOTE: We don't start nginx until after we finish installing aegir"))

# TODO: separate updating and configuring php
def update_php(php_version=''):
  print(green('>>> Update php'))

  print(green('>>>> Add php tap for homebrew'))
  homebrew_add_tap('josegonzalez/homebrew-php')

  print(green('>>>> Backup your original version of PHP, in the case you ever want to revert to a vanilla state. Note: You may need to repeat this step anytime you use combo updater to install OS X updates'))
  with settings(warn_only=True):
    if run("test -f /usr/bin/php-apple").failed:
      sudo('mv /usr/bin/php /usr/bin/php-apple')

  print(green('>>>> Execute the brew install process using hombrew-alt php brew file'))
  run('brew install php --with-mariadb --with-fpm')

  if (php_version == ''):
    php_version = run("brew info php --with-mariadb --with-fpm | grep ^php | sed 's/php //g'")

  print(green('>>>> Edit the fpm config file'))
  fpm_config = '/usr/local/etc/php-fpm.conf'
  run("sed -i.bak -E -e 's/^(%s.*)/;\\1/g' %s" % ('pid =', fpm_config))
  run("sed -i.bak -E -e 's/^(%s.*)/;\\1/g' %s" % ('user =', fpm_config))
  run("sed -i.bak -E -e 's/^(%s.*)/;\\1/g' %s" % ('group =', fpm_config))
  run("sed -i.bak -E -e 's/^(%s.*)/;\\1/g' %s" % ('pm.start_servers =', fpm_config))
  run("sed -i.bak -E -e 's/^(%s.*)/;\\1/g' %s" % ('pm.min_spare_servers =', fpm_config))
  run("sed -i.bak -E -e 's/^(%s.*)/;\\1/g' %s" % ('pm.max_spare_servers =', fpm_config))
  run("sed -i.bak -E -e 's/^(%s.*)/;\\1/g' %s" % ('pm.max_requests =', fpm_config))

  # Doesn't seem to like the pid directive, why? -- worked around via -g
  #run('echo "%s" >> %s' % ('pid = /usr/local/var/run/php-fpm.pid', fpm_config))
  run('echo "%s" >> %s' % ('user = _www', fpm_config))
  run('echo "%s" >> %s' % ('group = _www', fpm_config))
  run('echo "%s" >> %s' % ('pm.start_servers = 3', fpm_config))
  run('echo "%s" >> %s' % ('pm.min_spare_servers = 3', fpm_config))
  run('echo "%s" >> %s' % ('pm.max_spare_servers = 5', fpm_config))
  run('echo "%s" >> %s' % ('pm.max_requests = 500', fpm_config))

  print(green('>>>> Create directory and file for php-fpm log'))
  run('mkdir /usr/local/Cellar/php/%s/var/log/' % php_version)
  run('touch /usr/local/Cellar/php/%s/var/log/php-fpm.log' % php_version)

  print(green('>>>> Make our log file visible in Console app'))
  sudo('ln -s /usr/local/Cellar/php/%s/var/log/php-fpm.log /var/log/nginx/php-fpm.log' % php_version)

  php_config = '/usr/local/etc/php.ini'
  print(yellow('>>>> It is not safe to rely on the system\'s timezone settings.'))
  timezone = prompt(green('Please enter your timezone, see http://www.php.net/manual/en/timezones.php for a list:'), key=None, default='Australia/Melbourne', validate=None)
  run("sed -i.bak -E -e 's/^(%s.*)/;\\1/g' %s" % ('date.timezone =', php_config))
  run('echo "date.timezone = %s" >> %s' % (timezone, php_config))

  print(yellow('>>>> Set php memory_limit to 256M'))
  run("sed -i.bak -E -e 's/^(%s.*)/;\\1/g' %s" % ('memory_limit =', php_config))
  run('echo "%s" >> %s' % ('memory_limit = 256M', php_config))

  print(green('>>>> Download LaunchDaemon for php-fpm'))
  # TODO: Remove NetworkState from the plist?
  sudo('curl -fsSL https://raw.github.com/gist/1681635 > /System/Library/LaunchDaemons/org.homebrew.php-fpm.plist')
  sudo('launchctl load -w /System/Library/LaunchDaemons/org.homebrew.php-fpm.plist')

def install_drush(drush_version=''):
  print(green('>>> Install Drush'))

  if (drush_version == ''):
    # attempt to be clever with getting version number
    drush_version = run("curl -s http://drupal.org/node/97249/release/feed | grep '<title>drush 7.x-4' | sed -n 1p | sed -E 's/.*<title>drush (.*)<\/title>/\\1/g'")

  run('curl -O http://ftp.drupal.org/files/projects/drush-%s.tar.gz' % drush_version)
  run('gunzip -c drush-%s.tar.gz | tar -xf -' % drush_version)
  run('rm drush-%s.tar.gz' % drush_version)

  print(green('>>>> Make Drush accesible via your path'))
  run('ln -s ~/drush/drush /usr/local/bin/drush')

  print(green('>>>> Download drush_make'))
  username = run('whoami')
  run('drush dl drush_make-6.x --destination="/Users/%s/.drush"' % username)

# TODO: Support later than 6.x-1.x
def install_aegir(aegir_version=''):
  print(green('>>> Install Aegir'))
  print(green(">>>> We're in the home stretch now!"))
  print(green('>>>> Make a few small changes required for this to work properly'))

  if (aegir_version == ''):
    # attempt to be clever with getting version number
    aegir_version = run('curl -s http://drupal.org/node/195997/release/feed | grep "<title>hostmaster 6.x-1\." | sed -n 1p | sed -E "s/.*<title>hostmaster (.*)<\/title>/\\1/g"')

  if (aegir_version != ''):
    print(green('>>>> Install Aegir version: %s' % aegir_version))
  else:
    abort("Not sure what version of Aegir to install here...")

  username = run('whoami')
  with settings(warn_only=True):
    if local("test -d %s" % '/var/aegir').failed:
      sudo('mkdir /var/aegir')
  sudo('chown %s /var/aegir' % username)
  sudo('chgrp staff /var/aegir')
  sudo('dscl . append /Groups/_www GroupMembership %s' % username)

  print(green('>>>> Manually Install Drush and Aegir components'))

  # TODO: check if version string includes 6.x or 7.x
  print(green('>>>> Download provision'))
  run('drush dl provision-6.x --destination="/Users/%s/.drush"' % username)

  if (aegir_version < '6.x-1.7'):
    # Apply the following patch to provision until it is committed to aegir
    #http://drupalcode.org/sandbox/omega8cc/1111100.git/commit/a208ed4
    run('curl http://drupalcode.org/sandbox/omega8cc/1111100.git/patch/a208ed4 > /Users/%s/.drush/provision/nginx_mac.patch' % username)
    with cd('/Users/%s/.drush/provision' % username):
      run('patch -p1 < nginx_mac.patch')

  with settings(warn_only=True):
    print(green('>>>> Once nginx is compiled, backup the default nginx config'))
    run('mv /usr/local/etc/nginx/nginx.conf /usr/local/etc/nginx/nginx.conf.bak')
    print(green('>>>> Create nginx conf.d directory'))
    run('mkdir -p /usr/local/etc/nginx/conf.d')

  print(green('>>>> Downloading Nginx config'))
  nginx_config = '/usr/local/etc/nginx/nginx.conf'
  run('curl -fsSL https://raw.github.com/gist/1674935 > %s' % nginx_config)

  print(green('>>>> Edit the config to set your username, replace [username] on the third line with your own username'))
  username = run('whoami')
  run("sed -i.bak -E -e 's/\[username\]/%s/g' %s" % (username, nginx_config))

  print(green('>>>> Copy the LaunchDaemon config to load nginx into place'))
  sudo('curl -fsSL https://raw.github.com/gist/1679829 > /System/Library/LaunchDaemons/org.nginx.nginx.plist')
  sudo('launchctl load -w /System/Library/LaunchDaemons/org.nginx.nginx.plist')

  print(green('>>>> Install Hostmaster!'))
  run("drush hostmaster-install --aegir_root='/var/aegir' --root='/var/aegir/hostmaster-%s' --http_service_type=nginx --web_group=_www" % aegir_version)

  print(red('^^  Now copy the URL above as you will need it shortly, then lets install some ^^'))
  if (confirm('Copied it?', default=False)):
    print(green('>>>> Lets grab additional module/s for awesomeness! (you will still need to enable these within your hostmaster site)'))
    if (confirm('Shall we?', default=False)):
      print(green('>>>> Download aegir_backup_manager_ui'))
      if (confirm('Do you want aegir_backup_manager_ui added?', default=False)):
        run("git clone --branch 6.x-1.x http://git.drupal.org/sandbox/d1b1/1140744.git /var/aegir/hostmaster-%s/sites/%s/modules/aegir_backup_manager_ui" % (aegir_version, env.hostname))
        run("git clone --branch 6.x-1.x http://git.drupal.org/sandbox/d1b1/1140744.git /Users/%s/.drush/provision/aegir_backup_manager_ui" % username)
      print(green('>>>> Download hosting_backup_gc'))
      if (confirm('Do you want hosting_backup_gc added?', default=False)):
        run("git clone --branch 6.x-1.x http://git.drupal.org/project/hosting_backup_gc.git /var/aegir/hostmaster-%s/sites/%s/modules/hosting_backup_gc" % (aegir_version, env.hostname))
      print(green('>>>> Download hosting_backup_queue'))
      if (confirm('Do you want hosting_backup_queue added?', default=False)):
        run("git clone --branch 6.x-1.x http://git.drupal.org/project/hosting_backup_queue.git /var/aegir/hostmaster-%s/sites/%s/modules/hosting_backup_queue" % (aegir_version, env.hostname))
      print(green('>>>> Download hosting_platform_pathauto'))
      if (confirm('Do you want hosting_platform_pathauto added?', default=False)):
        run("git clone --branch 6.x-1.x http://git.drupal.org/project/hosting_platform_pathauto.git /var/aegir/hostmaster-%s/sites/%s/modules/hosting_platform_pathauto" % (aegir_version, env.hostname))
      print(green('>>>> Download hosting_queue_runner'))
      if (confirm('Do you want hosting_queue_runner added?', default=False)):
        run("git clone --branch 6.x-1.x http://git.drupal.org/project/hosting_queue_runner.git /var/aegir/hostmaster-%s/sites/%s/modules/hosting_queue_runner" % (aegir_version, env.hostname))
        #TODO: create plist to actually run hosting_queue_runner
      print(green('>>>> Download hosting_remote_import and remote_import'))
      if (confirm('Do you want remote_import added?', default=False)):
        run("git clone --branch 6.x-1.x http://git.drupal.org/project/hosting_remote_import.git /var/aegir/hostmaster-%s/sites/%s/modules/hosting_remote_import" % (aegir_version, env.hostname))
        run("git clone --branch 6.x-1.x https://github.com/omega8cc/remote_import.git /Users/%s/.drush/provision/remote_import" % username)

  print(green('>>>> Remove the default platforms dir and create a symlink for so you can put your Platforms in ~/Sites/ directory'))
  with settings(warn_only=True):
    run('mkdir -p /Users/%s/Sites' % username)
  run('rmdir /var/aegir/platforms')
  run('ln -s /Users/%s/Sites /var/aegir/platforms' % username)

  print(green('>>>> Create symbolic link for aegir vhosts'))
  with settings(warn_only=True):
    run('ln -fns /var/aegir/config/nginx.conf /usr/local/etc/nginx/conf.d/aegir.conf')

  sudo('/usr/local/sbin/nginx -s reload')

  print(green('>>>> Open your web browser and start creating platforms and sites!'))
  hostname = run('hostname -f')
  print(green('>>>> http://%s' % hostname))

