# Realising MSSH.chrono

After continuous use and development over the last months MSSH.chrono finally gets its first official release. This release is (probably) neither bug-free nor complete. It does however have all the core functionality that is planned for the near future AND all the data collected in this version will be useable in future releases.

## Chrono does things

Chrono is saving, managing and analyzing your day, deadlines and sleep patterns. Chrono requires no connection to the internet<sup id="a1">[1](#f1)</sup> and doesn't share any of your data! Chrono works best if it has a wide variety of data, but only one kind of data is needed for Chrono to be useful. The core idea is to split each day into ChronoEvents. You can visualize your days or check for patterns in your behavior. You could for example use the "heatmap" and "plot" commands to check how you manage your time around deadlines or to analyze the time frames in which you typically do X. 
![Plot](/images/plot.png)
![Heatmap of a particular subject](/images/heatmap.png)

Chrono is a command line. There are no buttons, just you and your keyboard. There is no need to search through nested menus because every command needs at most 1 previous command("setr") to work! If you feel like you are typing the same command over and over again while only changing one argument, Chrono also features aliases (including currying!) to eliminate such repetitive inputs. 

Aliases give you the option to customize Chrono in a meaningful way. Aliases support a pipe operator (think a simplified version of f#'s |>), partial function application, (limited) splicing and even simple higher-order functions<sup id="a2">[2](#f2)</sup>. This should enable you to optimize your workflow immensely.

## Reasons why you should use Chrono

Chrono is build in a way that tries to minimize the time in which you use Chrono. Aliases, the CLI-nature of Chrono and the design of the commands all contribute to this goal.
I have personally used Chrono for the last semester, adding features as I needed them. Therefore Chrono doesn't come from a room full of designers, but from a user. While there is a vision, as well as a design philosophy behind the development of Chrono, most features (beyond the original vision) come from a real-life need. If you believe any features are missing feel free to add them yourself or email me @ "mh[at][domain]". If I also like the feature I will add it.

Reminder: Chrono is open-source, so if you are missing a simple feature you can add it in no time ! You can also use Chrono to collect your data and then analyze it yourself because Chrono saves your data in a (hopefully) well documented .json file.

## Footnotes

<b id="f1">1</b> If you want to use data imported from your oura ring, you obviously need an internet connection for the duration of the import.[↩](#a1)

<b id="f2">2</b> The lhof / rhof commands are higher-order functions, which only exist to enable such a feature. These commands serve no purpose on their own.[↩](#a2)


