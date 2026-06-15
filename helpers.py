def cprint(msg, color="reset"):
    codes = {
        "reset":   "\033[0m",
        "red":     "\033[31m",
        "green":   "\033[32m",
        "yellow":  "\033[33m",
        "blue":    "\033[34m",
        "magenta": "\033[35m",
        "cyan":    "\033[36m",
        "white":   "\033[37m",
        "bold":    "\033[1m",
    }
    print(f"{codes.get(color, '')}{msg}{codes['reset']}")
