from fabric.api import *
from fabric.colors import green, red, yellow
from fabric.contrib.console import confirm
from fabric.contrib.files import *
import random, re, string, sys, time

time = time.strftime('%Y%m%d-%H%M')

# TODO: fabric bug: osx uses -E instead of -r, this means sed(), comment(), and uncomment() won't work properly
# TODO: Get the aegir, drush, mariadb, and php versions in some clever way (but override if needed?)

def install(aegir_version, php_version, hostname = '', type='beginning'):
  env.arguments = "%s, %s, hostname = ''" % (aegir_version, php_version)
  if (type == 'beginning'):
    check_requirements()
    install_homebrew()
    update_hosts(hostname)
    set_hostname(hostname)
    install_nginx()
    install_mariadb(mariadb_version)
    update_php()
    configure_daemons()
  if (type == 'end'):
    configure_mariadb()
    install_drush(drush_version)
    install_aegir(aegir_version, hostname)

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
  print(green('>>>> Now go back to your terminal window and type the following to install Homebrew'))

  if (not confirm('Is XCode installed?', default=False)):
    abort('XCode is required by Homebrew')

def check_homebrew():
  print(green('>>> Install the requirements for this process; Homebrew'))

  # TODO: install homebrew
  #run('ruby -e "$(curl -fsSL https://raw.github.com/gist/323731)"') <-- doesn't work via run at the moment?
  # the press enter to continue bit?

  if (not confirm('Is homebrew installed?', default=False)):
    abort('Homebrew is required')
    #install_homebrew()

def install_homebrew():
  print(yellow('>>>> Download homebrew-alt so we can rebuild php with the required components'))
  run('git clone https://github.com/adamv/homebrew-alt.git /usr/local/LibraryAlt')
  with settings(warn_only=True):
    if run("test -f %s" % '~/.bash_profile').failed:
      run('echo "PATH=$PATH:/usr/local/sbin; export PATH" > ~/.bash_profile')
    else:
      append("~/.bash_profile", 'PATH=$PATH:/usr/local/sbin; export PATH', use_sudo=False)

def update_hosts(domain, ip='127.0.0.1'):
  hosts = '/etc/hosts'
  if (contains(hosts, domain)):
    # Comment existing hosts entry for that domain
    # TODO: NOT! if it's localhost
    sudo("sed -i.bak -E -e 's/(^.*%s)/#\\1/g' /etc/hosts" % domain)
  sudo('echo "%s  %s" >> /etc/hosts' % (ip, domain))

def set_hostname(hostname=''):
  if confirm('Do you want to change/set your hostname?', default=True):
    print(green(">>>> Set hostname as it's required for sane default in aegir setup, we chose rl.ld for Realityloop Local Development you can use something else instead of rl but it needs to end in .ld"))
    if (hostname == ''):
      current_hostname = run('hostname')
      hostname = prompt('Please enter your desired hostname:', key=None, default=current_hostname, validate=None)
    sudo('scutil --set HostName %s' % hostname)

def install_nginx():
  print(green('>>> Setting up Nginx'))
  print(green('>>>> Prevent apache from being loaded automatically'))
  sudo('launchctl unload -w /System/Library/LaunchDaemons/org.apache.httpd.plist')

  # TODO: the sed doesn't seem to be working / dislikes the newline in the replacement string
  '''
  print(green('>>>> Modify homebrew recipe to add debugging'))
  nginx_recipe = '/usr/local/Library/Formula/nginx.rb'
  if (not contains(nginx_recipe, '--with-debug')):
    # sed -i.bak -E -e 's/(args = \["--prefix=#{prefix}",)/\n"--with-debug",/g' nginx.rb
    sudo('sed -i.bak -E -e \'s/(\s+args = \["--prefix=#{prefix}",\n)/\1            "--with-debug",/g\' %s' % nginx_recipe)
  '''

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

def install_mariadb():
  print(green('>>> Install MariaDB'))
  print(green('>>>> MariaDB is a community-developed branch of the MySQL database, the impetus being the community maintenance of its free status under GPL, as opposed to any uncertainty of MySQL license status under its current ownership by Oracle.'))
  print(green('>>>> The intent also being to maintain high fidelity with MySQL, ensuring a "drop-in" replacement capability with library binary equivalency and exacting matching with MySQL APIs and commands. It includes the XtraDB storage engine as a replacement for InnoDB.'))

  run('brew install mariadb')

  print(green('>>>> Once compilation has finished unset TMPDIR'))
  run('unset TMPDIR')

  print(green('>>>> Then mysql_install_db'))
  sudo('mysql_install_db')
  print(green(">>>> but don't follow any more of the prompts just now or you will run into problems, we'll do the rest later."))

def update_php(php_version):
  print(green('>>> Update php'))

  print(green('>>>> Backup your original version of PHP, in the case you ever want to revert to a vanilla state. Note: You may need to repeat this step anytime you use combo updater to install OS X updates'))
  sudo('mv /usr/bin/php /usr/bin/php-apple')

  print(green('>>>> Execute the brew install process using hombrew-alt php brew file'))
  run('brew install /usr/local/LibraryAlt/duplicates/php.rb --with-mysql --with-fpm')

  print(green('>>>> Once compilation is complete create your php-fpm config file'))
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

  print(green('>>>> Create directory and file for php-fpm log'))
  sudo('mkdir /usr/local/Cellar/php/%s/var/log/' % php_version)
  sudo('touch /usr/local/Cellar/php/%s/var/log/php-fpm.log' % php_version)

  print(green('>>>> Make our log file visible in Console app'))
  sudo('ln -s /usr/local/Cellar/php/%s/var/log/php-fpm.log /var/log/nginx/php-fpm.log' % php_version)

  print(green('>>>> Set your timezone in php.ini http://www.php.net/manual/en/timezones.php'))

# TODO
  print(yellow('$ nano /usr/local/etc/php.ini'))
  print(yellow('I added the follwing under the ;date.timezone = line'))
  print(yellow('date.timezone = Australia/Melbourne'))

  # TODO: test this replacement
  php_config = '/usr/local/etc/php.ini'
  print(yellow('>>>> Set php memory_limit to 256M'))
  sudo("sed -i.bak -E -e 's/(memory_limit = ).*/\\256M/g' %s" % php_config)

def configure_daemons(mariadb_version):
  print(green('>>> Configure Service Launch Daemons'))
  print(green('>>>> This is so everything runs automatically on startup'))

  print(green('>>>> Download the LaunchDaemon to load nginx on boot'))
  sudo('curl http://realityloop.com/sites/realityloop.com/files/uploads/nginx.plist_.txt > /System/Library/LaunchDaemons/org.homebrew.nginx.plist')

  print(green('>>>> Download LaunchDaemon for php-fpm'))
  sudo('curl http://realityloop.com/sites/realityloop.com/files/uploads/php-fpm.plist_.txt > /System/Library/LaunchDaemons/org.homebrew.php-fpm.plist')

  print(green('>>>> Copy the LaunchDaemon to load mariadb on boot into place'))
  sudo('cp /usr/local/Cellar/mariadb/%s/com.mysql.mysqld.plist /System/Library/LaunchDaemons/com.mysql.mysqld.plist' % mariadb_version)

  print(yellow('Restart your computer to enable the services Yes you really need to do this now, or the next step will not work'))
  print(red('After restart, you can continue the installation by running: fab -H [hostname] %s' % env.arguments))

def configure_mariadb(mariadb_version):
  print(green('>>> Answer the prompts as follows, replace [password] with a password of your own chosing'))
  print(yellow('>>>> Enter current password for root (enter for none): [Enter]'))
  print(yellow('>>>> Set root password? [Y/n] y'))
  print(yellow('>>>> New password: [password]'))
  print(yellow('>>>> Re-enter new password: [password]'))
  print(yellow('>>>> Remove anonymous users? [Y/n] y'))
  print(yellow('>>>> Disallow root login remotely? [Y/n] y'))
  print(yellow('>>>> Remove test database and access to it? [Y/n] y'))
  print(yellow('>>>> Reload privilege tables now? [Y/n] y'))

  sudo('/usr/local/Cellar/mariadb/%s/bin/mysql_secure_installation' % mariadb_version)

def install_drush(drush_version):
  print(green('>>> Install Drush'))

  #run('export DRUSH_VERSION=7.x-4.5')
  run('curl -O http://ftp.drupal.org/files/projects/drush-%s.tar.gz' % drush_version)
  run('gunzip -c drush-%s.tar.gz | tar -xf -' % drush_version)
  run('rm drush-%s.tar.gz' % drush_version)

  print(green('>>>> Make Drush accesible via your path'))
  sudo('ln -s ~/drush/drush /usr/local/bin/drush')

  print(green('>>>> Download drush_make'))
  run('drush dl drush_make-6.x --destination="/users/`whoami`/.drush"')

def install_aegir(aegir_version, hostname=''):
  print(green('>>> Install Aegir'))
  print(green('>>>> our in the home stretch now!'))
  print(green('>>>> Make a few small changes required for this to work properly'))

  sudo('mkdir /var/aegir')
  sudo('chown `whoami` /var/aegir')
  sudo('chgrp staff /var/aegir')
  sudo('dscl . append /Groups/_www GroupMembership `whoami`')

  print(green('>>>> Manually Install Drush and Aegir components'))

  # TODO: check if version string includes 6.x or 7.x
  print(green('>>>> Download provision'))
  run('drush dl provision-6.x --destination="/users/`whoami`/.drush"')

  #Apply the following patch to provision until version 6.x-1.5 of aegir comes out
  #http://drupalcode.org/sandbox/omega8cc/1111100.git/commit/a208ed4

  print(green('>>>> Install Hostmaster!'))
  run("drush hostmaster-install --aegir_root='/var/aegir' --root='/var/aegir/hostmaster-%s' --http_service_type=nginx" % aegir_version)

  print(green('>>>> Remove the default platforms dir and create a symlink for so you can put your Platforms in ~/Sites/ directory'))
  run('mkdir /Users/`whoami`/Sites')
  run('rmdir /var/aegir/platforms')
  run('ln -s /Users/`whoami`/Sites /var/aegir/platforms')

  print(green('>>>> Open your web browser and start creating platforms and sites!'))
  if (hostname == ''):
    hostname = run('hostname -f')
  print(green('>>>> http://%s' % hostname))

