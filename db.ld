ld. 7200    IN       SOA     dev. root.ld. (
             2008031801 ;    Serial
             15      ; Refresh every 15 minutes
             3600    ; Retry every hour
             3000000 ; Expire after a month+
             86400 ) ; Minimum ttl of 1 day
             IN      NS      ld.
             IN      MX      10 ld.
 
             IN      A       127.0.0.1
*.ld.        IN      A       127.0.0.1
