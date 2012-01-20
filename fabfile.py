from fabric.api import *
from fabric.colors import green, red, yellow
from fabric.contrib.console import confirm
from fabric.contrib.files import *
import random, re, string, sys, time

time = time.strftime('%Y%m%d-%H%M')

# TODO: fabric bug: osx uses -E instead of -r, this means sed(), comment(), and uncomment() won't work properly
# TODO: Get the aegir, drush, mariadb, and php versions in some clever way (but override if needed?)
# TODO: perl inline replacement: perl -p -i.bak -e "s#a#b#" filename

def install(aegir_version='', hostname='', type='beginning'):
  env.arguments = "%s, hostname = '%s'" % (aegir_version, hostname)
  env.hostname = hostname
  if (type == 'beginning'):
    check_requirements()
    set_hostname()
    install_nginx()
    install_mariadb()
  if (type == 'end'):
    update_php()
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

def install_homebrew():
  print(green('>>> Install Homebrew'))
  run('ruby -e "$(curl -fsSL https://raw.github.com/gist/323731)"')

  print(yellow('>>>> Download homebrew-alt so we can rebuild php with the required components'))

  homebrew_alt_dir = '/usr/local/LibraryAlt'
  with settings(warn_only=True):
    if local("test -d %s" % homebrew_alt_dir).failed:
      run('git clone https://github.com/adamv/homebrew-alt.git %s' % homebrew_alt_dir)

  with cd(homebrew_alt_dir):
    # put git status check here
    run('git pull')

  path_update = 'PATH=$PATH:/usr/local/sbin; export PATH'
  with settings(warn_only=True):
    if run("test -f %s" % '~/.bash_profile').failed:
      run('echo "%s" > ~/.bash_profile' % path_update)
    else:
      # TODO: check if this already exists first
      append("~/.bash_profile", '%s' % path_update, use_sudo=False)

def update_hosts(domain='', ip='127.0.0.1'):
  hosts = '/etc/hosts'
  if (domain == ''):
    domain = run('hostname -f')
  if (domain != 'localhost' and contains(hosts, domain)):
    # Comment existing hosts entry for that domain
    # TODO: NOT! if it's localhost
    # TODO: fix the escaping here
    sudo("sed -i.bak -E -e 's/(.*%s)/#\\1/g' /etc/hosts" % domain)
  sudo('echo "%s  %s" >> /etc/hosts' % (ip, domain))

def set_hostname(hostname=''):
  current_hostname = run('hostname -f')

  print(green(">>>> Set hostname as it's required for sane default in aegir setup, we chose rl.ld for Realityloop Local Development you can use something else instead of rl but it needs to end in .ld"))

  if confirm('Your current hostname is %s, do you want to change your hostname?' % current_hostname, default=False):
    if (hostname != ''):
      env.hostname = hostname
    else:
      current_hostname = run('hostname -f')
      env.hostname = prompt('Please enter your desired hostname:', key=None, default=current_hostname, validate=None)
    sudo('scutil --set HostName %s' % hostname)
    update_hosts()

def install_nginx():
  print(green('>>> Setting up Nginx'))
  print(green('>>>> Prevent apache from being loaded automatically'))
  sudo('launchctl unload -w /System/Library/LaunchDaemons/org.apache.httpd.plist')

  print(green('>>>> Modify homebrew recipe to add debugging'))
  nginx_recipe = '/usr/local/Library/Formula/nginx.rb'
  if (not contains(nginx_recipe, '--with-debug')):
    run('perl -p -i.bak -e \'s/(args = \["--prefix=#{prefix}",)/\\1\n            "--with-debug",/g\' %s' % nginx_recipe)

  run('brew install nginx')

  print(green('>>>> Once nginx is compiled, backup the default nginx config'))
  sudo('mv /usr/local/etc/nginx/nginx.conf /usr/local/etc/nginx/nginx.conf.bak')

  print(green('>>>> Downloading Nginx config from realityloop'))
  nginx_config = '/usr/local/etc/nginx/nginx.conf'
  sudo('curl http://realityloop.com/sites/realityloop.com/files/uploads/nginx.conf_.txt > %s' % nginx_config)

  print(green('>>>> Edit the config to set your username, replace [username] on the third line with your own username'))
  sudo("sed -i.bak -E -e 's/\[username\]/`whoami`/g' %s" % nginx_config)

  print(green('>>>> Make nginx log files visible in Console app'))
  sudo('mkdir /var/log/nginx')

  print(green('>>>> Create the following directorty to stop "/var/lib/nginx/speed" failed (2: No such file or directory) error'))
  sudo('mkdir /var/lib/nginx')

  print(green('>>>> Allow your user to restart nginx.'))
  sudo('echo "`whoami` ALL=NOPASSWD: /usr/local/sbin/nginx" >> /etc/sudoers')

  print(green('>>>> Create symbolic link for aegir vhosts'))
  sudo('ln -s /var/aegir/config/nginx.conf /usr/local/etc/nginx/aegir.conf')

  print(green('>>>> Download the LaunchDaemon to load nginx on boot'))
  sudo('curl http://realityloop.com/sites/realityloop.com/files/uploads/nginx.plist_.txt > /System/Library/LaunchDaemons/org.homebrew.nginx.plist')

def install_mariadb(mariadb_version=''):
  print(green('>>> Install MariaDB'))
  print(green('>>>> MariaDB is a community-developed branch of the MySQL database, the impetus being the community maintenance of its free status under GPL, as opposed to any uncertainty of MySQL license status under its current ownership by Oracle.'))
  print(green('>>>> The intent also being to maintain high fidelity with MySQL, ensuring a "drop-in" replacement capability with library binary equivalency and exacting matching with MySQL APIs and commands. It includes the XtraDB storage engine as a replacement for InnoDB.'))

  run('brew install mariadb')

  if (mariadb_version == ''):
    mariadb_version = run("brew info mariadb | grep ^mariadb | sed 's/mariadb //g'")

  print(green('>>>> Once compilation has finished unset TMPDIR'))
  print(green('>>>> Then mysql_install_db'))
  run('unset TMPDIR && /usr/local/Cellar/mariadb/%s/bin/mysql_install_db' % mariadb_version)

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

  # TODO: Test if this works post-restart
  print(green('>>>> Copy the LaunchDaemon to load mariadb on boot into place'))
  sudo('cp /usr/local/Cellar/mariadb/%s/com.mysql.mysqld.plist /System/Library/LaunchDaemons/com.mysql.mysqld.plist' % mariadb_version)
  sudo('launchctl load -w /System/Library/LaunchDaemons/com.mysql.mysqld.plist')


  '''
  run('mkdir ~/Library/LaunchAgents')
  run('cp -vi /usr/local/Cellar/mariadb/5.2.8/com.mysql.mysqld.plist ~/Library/LaunchAgents/')
  run('launchctl load -w ~/Library/LaunchAgents/com.mysql.mysqld.plist')
  #print(green(">>>> but don't follow any more of the prompts just now or you will run into problems, we'll do the rest later."))

  print(yellow('Restart your computer to enable the services Yes you really need to do this now, or the next step will not work'))
  print(red('After restart, you can continue the installation by running: fab -H [hostname] %s' % env.arguments))
  '''

def update_php(php_version=''):
  print(green('>>> Update php'))

  print(green('>>>> Backup your original version of PHP, in the case you ever want to revert to a vanilla state. Note: You may need to repeat this step anytime you use combo updater to install OS X updates'))
  sudo('mv /usr/bin/php /usr/bin/php-apple')

  print(green('>>>> Execute the brew install process using hombrew-alt php brew file'))
  run('brew install /usr/local/LibraryAlt/duplicates/php.rb --with-mysql --with-fpm')

  print(green('>>>> Once compilation is complete create your php-fpm config file'))
  if (php_version == ''):
    php_version = run("brew info /usr/local/LibraryAlt/duplicates/php.rb --with-mysql --with-fpm | grep ^php | sed 's/php //g'")
  sudo('cp /usr/local/Cellar/php/%s/etc/php-fpm.conf.default /usr/local/Cellar/php/%s/etc/php-fpm.conf' % (php_version, php_version))

  print(green('>>>> Create symbolic link for it in /usr/local/etc/'))
  sudo('ln -s /usr/local/Cellar/php/%s/etc/php-fpm.conf /usr/local/etc/php-fpm.conf' % php_version)

  print(green('>>>> Edit the conf file'))

# TODO
  fpm_config = '/usr/local/etc/php-fpm.conf'
  print(yellow('$ nano /usr/local/etc/php-fpm.conf'))
  print(yellow('Add the following line below ;pid = run/php-fpm.pid'))
  print(yellow('pid = /usr/local/var/run/php-fpm.pid'))
  print(yellow('Update the user and group section as follows'))
  print(yellow('user = _www'))
  print(yellow('group = _www'))
  print(yellow('Remove the ; from the start of the following lines then save using Ctrl+X then Y'))
  print(yellow('pm.start_servers = 3'))
  print(yellow('pm.min_spare_servers = 3'))
  print(yellow('pm.max_spare_servers = 5'))
  print(yellow('pm.max_requests = 500'))

  sudo("sed -i.bak -E -e 's/^(%s.*)/;\\1/g' %s" % ('pid =', fpm_config))
  sudo("sed -i.bak -E -e 's/^(%s.*)/;\\1/g' %s" % ('user =', fpm_config))
  sudo("sed -i.bak -E -e 's/^(%s.*)/;\\1/g' %s" % ('group =', fpm_config))
  sudo("sed -i.bak -E -e 's/^(%s.*)/;\\1/g' %s" % ('pm.start_servers =', fpm_config))
  sudo("sed -i.bak -E -e 's/^(%s.*)/;\\1/g' %s" % ('pm.min_spare_servers =', fpm_config))
  sudo("sed -i.bak -E -e 's/^(%s.*)/;\\1/g' %s" % ('pm.max_spare_servers =', fpm_config))
  sudo("sed -i.bak -E -e 's/^(%s.*)/;\\1/g' %s" % ('pm.max_requests =', fpm_config))

  sudo('echo "%s" >> %s' % ('pid = /usr/local/var/run/php-fpm.pid', fpm_config))
  sudo('echo "%s" >> %s' % ('user = _www', fpm_config))
  sudo('echo "%s" >> %s' % ('group = _www', fpm_config))
  sudo('echo "%s" >> %s' % ('pm.start_servers = 3', fpm_config))
  sudo('echo "%s" >> %s' % ('pm.min_spare_servers = 3', fpm_config))
  sudo('echo "%s" >> %s' % ('pm.max_spare_servers = 5', fpm_config))
  sudo('echo "%s" >> %s' % ('pm.max_requests = 500', fpm_config))

  print(green('>>>> Create directory and file for php-fpm log'))
  sudo('mkdir /usr/local/Cellar/php/%s/var/log/' % php_version)
  sudo('touch /usr/local/Cellar/php/%s/var/log/php-fpm.log' % php_version)

  print(green('>>>> Make our log file visible in Console app'))
  sudo('ln -s /usr/local/Cellar/php/%s/var/log/php-fpm.log /var/log/nginx/php-fpm.log' % php_version)

  print(green('>>>> You may want to set your timezone in php.ini http://www.php.net/manual/en/timezones.php'))
  print(yellow('$ nano /usr/local/etc/php.ini'))
  print(yellow('I added the follwing under the ;date.timezone = line'))
  print(yellow('date.timezone = Australia/Melbourne'))

  # TODO: test this replacement
  php_config = '/usr/local/etc/php.ini'
  print(yellow('>>>> Set php memory_limit to 256M'))
  sudo("sed -i.bak -E -e 's/^(%s.*)/;\\1/g' %s" % ('memory_limit =', php_config))
  sudo('echo "%s" >> %s' % ('memory_limit = 256M', php_config))

  print(green('>>>> Download LaunchDaemon for php-fpm'))
  sudo('curl http://realityloop.com/sites/realityloop.com/files/uploads/php-fpm.plist_.txt > /System/Library/LaunchDaemons/org.homebrew.php-fpm.plist')

def install_drush(drush_version=''):
  print(green('>>> Install Drush'))

  if (drush_version == ''):
    # attempt to be clever with getting version number
    drush_version = run("curl -s http://drupal.org/node/97249/release/feed | grep '<title>drush 7.x-4' | sed -n 1p | sed -E 's/.*<title>drush (.*)<\/title>/\\1/g'")

  #run('export DRUSH_VERSION=7.x-4.5')
  run('curl -O http://ftp.drupal.org/files/projects/drush-%s.tar.gz' % drush_version)
  run('gunzip -c drush-%s.tar.gz | tar -xf -' % drush_version)
  run('rm drush-%s.tar.gz' % drush_version)

  print(green('>>>> Make Drush accesible via your path'))
  sudo('ln -s ~/drush/drush /usr/local/bin/drush')

  print(green('>>>> Download drush_make'))
  run('drush dl drush_make-6.x --destination="/Users/`whoami`/.drush"')

def install_aegir(aegir_version=''):
  print(green('>>> Install Aegir'))
  print(green('>>>> our in the home stretch now!'))
  print(green('>>>> Make a few small changes required for this to work properly'))

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
  run('drush dl provision-6.x --destination="/Users/`whoami`/.drush"')

  #Apply the following patch to provision until version 6.x-1.5 of aegir comes out
  #http://drupalcode.org/sandbox/omega8cc/1111100.git/commit/a208ed4

  if (aegir_version == ''):
    # attempt to be clever with getting version number
    aegir_version = run("curl -s http://drupal.org/node/195997/release/feed | grep '<title>hostmaster 6.x' | sed -n 1p | sed -E 's/.*<title>hostmaster (.*)<\/title>/\\1/g'")

  print(green('>>>> Install Hostmaster!'))
  run("drush hostmaster-install --aegir_root='/var/aegir' --root='/var/aegir/hostmaster-%s' --http_service_type=nginx" % aegir_version)

  print(green('>>>> Remove the default platforms dir and create a symlink for so you can put your Platforms in ~/Sites/ directory'))
  run('mkdir /Users/`whoami`/Sites')
  run('rmdir /var/aegir/platforms')
  run('ln -s /Users/`whoami`/Sites /var/aegir/platforms')

  # TODO: nginx invalid option reload

  print(green('>>>> Open your web browser and start creating platforms and sites!'))
  hostname = run('hostname -f')
  print(green('>>>> http://%s' % hostname))

