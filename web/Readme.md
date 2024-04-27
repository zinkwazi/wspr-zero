# Securing WSPR-zero Data Files with `.htaccess`

This guide describes how to rename and configure an existing file as `.htaccess` to secure the `pi_data.json` file used by the WSPR-zero index.php portal, ensuring it is not directly accessible via the web.

## Step 1: Rename the Existing File to `.htaccess`

You need to rename the enclosed htaccess file to `.htaccess`. This can be done using the command line or SFTP.

### Using the Command Line

Navigate to the directory containing your file. Then use the `mv` command to rename your file. If your existing file has a name like `example.txt`, you would use:

```bash
mv htaccess.txt .htaccess

