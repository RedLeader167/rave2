#!/usr/bin/python3.9
import sys
import os
import string
import colorama
colorama.init()
class LexerErr(Exception):
    pass
class ICtxErr(Exception):
    pass

clrGreen = "\x1b[1;32;40m"
clrReset = "\x1b[0m"
clrBlue = "\x1b[1;34;40m"
clrOrange = "\x1b[1;33;40m"
clrRed = "\x1b[1;31;40m"

versions = {
    "early": "Slums",
    "pre1": "Duvaune",
    "1.0": "Kuro1",
    "1.1": "Manneban",
    "future": "Yume"
}

VERSIONID = "1.1"
VERSIONSMALL = "3"
VCX = clrOrange
VERSION = f"{VERSIONID}-{VERSIONSMALL} ({clrOrange}{versions[VERSIONID]}{clrReset})"

class ManagedStack:
    def __init__(self, pstack=None):
        self.stack = pstack if pstack is not None else []

    def push(self, item):
        if isinstance(item, int) or isinstance(item, float):
            self.stack.append(["int", item])
        elif isinstance(item, str):
            self.stack.append(["str", item])
        else:
            if item[0] in ("str", "lambda", "int"):
                self.stack.append(item)
            else:
                raise ICtxErr(f"Invalid push of {item[0]} - ictx bug?")

    def pop(self):
        if len(self.stack) > 0:
            return self.stack.pop()
        else:
            raise ICtxErr(f"Stack was empty, and program tried to pop")

class ManagedVar:
    def __init__(self, ptable=None):
        self.table = ptable if ptable is not None else {}

    def __getitem__(self, key):
        if key in self.table:
            return self.table[key]
        else:
            raise ICtxErr("Taking undeclared variable value")
    def __setitem__(self, key, value):
        if value[0] in ("lambda", "str", "int"):
            self.table[key] = value
        else:
            raise ICtxErr(f"Invalid set of {value[0]} - ictx bug?")

class Lexer:
    def __init__(self, text):
        self.text = text + " "
        self.ch = None
        self.idx = -1
        self.next()

    def next(self, step=1):
        self.idx += step
        self.ch = self.text[self.idx] if self.idx < len(self.text) else None

    def run(self):
        tokens = []
        while self.ch != None:
            token = self.process()
            if token is not None:
                tokens.append(token)
        return tokens

    def process(self):
        if self.ch in "0123456789":
            s = "" + self.ch
            self.next()
            while self.ch in "0123456789.":
                s += self.ch
                self.next()
            if s.count(".") == 0:
                s = int(s)
            elif s.count(".") < 2:
                s = float(s)
            else:
                raise LexerErr("Invalid number")
            # additional check for floats, that ends with .0
            if isinstance(s, float):
                if s.is_integer():
                    s = int(s)
            # for compatibility reasons, any numbers are "int".
            return ["int", s]
        elif self.ch in "\"'":
            table = {
                "0": "\0",
                "n": "\n",
                "t": "\t",
                "r": "\r",
                "\\": "\\",
                "e": "\x1b"
            }
            q = self.ch
            s = ""
            self.next()
            while self.ch != q:
                if self.ch is None:
                    raise LexerErr("String not closed")
                if self.ch == "\\":
                    self.next()
                    if self.ch in table:
                        s += table.get(self.ch, self.ch)
                    else:
                        raise LexerErr("There is no escape for " + self.ch+ ", however, if you think this is a mistake, create an issue or a pull request at our GitHub.")
                else:
                    s += self.ch
                self.next()
            self.next()
            return ["str", s]
        elif self.ch in string.ascii_lowercase + "`~!@#$%^&*()-_=+\\|/{},.<>?":
            return self.parseI(string.ascii_lowercase, "call")
        elif self.ch in string.ascii_uppercase:
            return self.parseI(string.ascii_uppercase, "var")
        elif self.ch in ";:":
            raise LexerErr(f"Usage of {self.ch} without variable")
        elif self.ch in " \r\n\t":
            self.next()
        elif self.ch == "[":
            braces = 0
            self.next()
            tokens = []
            while True:
                if self.ch == "[":
                    braces += 1
                elif self.ch == "]":
                    braces -= 1
                    if braces == -1:
                        break
                token = self.process()
                if token is not None:
                    tokens.append(token)
            self.next()
            return ["lambda", tokens]
        elif self.ch == "]":
            raise LexerErr(f"] used without [, maybe you forgot [ sign?")
        else:
            raise LexerErr(f"Invalid character '{self.ch}'")
        return None

    def parseI(self, fltr, name):
        s = "" + self.ch
        self.next()
        if name == "var":
            while self.ch in fltr:
                s += self.ch
                self.next()
            if self.ch == ":":
                self.next()
                return ["varassign", s]
            elif self.ch == ";":
                self.next()
                return ["varread", s]
            else:
                raise LexerErr("Incorrect variable usage - maybe you forgot ; or : ?")
        else:
            return [name, s]

class ICtx:
    def __init__(self, prg, debuggable, parentstack=None, parentvar=None, iInstance=0):
        self.prg = prg
        self.ptr = -1
        self.inst = iInstance
        self.stack = parentstack if parentstack is not None else ManagedStack()
        self.vartable = parentvar if parentvar is not None else ManagedVar()
        self.cmd = None
        self.dbg = debuggable
        self.next()

    def debug(self, text):
        if self.dbg:
            print(f"[* Interpreter Debug {self.inst}] {text}")

    def next(self, step=1):
        self.ptr += 1
        self.cmd = self.prg[self.ptr] if self.ptr < len(self.prg) else None

    def run(self):
        while self.cmd != None:
            self.process()
        self.debug(f"stack after executing: {self.stack.stack}")
        return self.stack, self.vartable

    def process(self):
        self.debug(f"stack: {self.stack.stack}")
        if self.cmd[0] in ("lambda", "int", "str"):
            self.stack.push(self.cmd)
            self.debug(f"Pushed {self.cmd[0]} on stack.")
            self.next()
        elif self.cmd[0] == "call":
            cl = self.cmd[1]
            if cl == "~":
                self.debug(f"Lambda called - creating new ICtx and passing it current context.")
                self.debug(f"Stack before call: {self.stack.stack}")
                lmbd = self.stack.pop()
                if lmbd[0] != "lambda":
                    raise ICtxErr("Call for non-lambda value")
                ctx = ICtx(lmbd[1], self.dbg, self.stack, self.vartable, self.inst + 1)
                ctx.run()
                self.debug(f"Stack after call: {self.stack.stack}")
                self.next()
            elif cl == "#":
                self.debug(f"Lambda while loop")
                body = self.stack.pop()
                cond = self.stack.pop()
                if cond[0] != "lambda" or body[0] != "lambda":
                    raise ICtxErr(f"While loop for non lambdas")
                while True:
                    self.debug("Checking cond")
                    ctx = ICtx(cond[1], self.dbg, self.stack, self.vartable, self.inst + 1)
                    ctx.run()
                    condval = self.stack.pop()
                    if condval[0] != "int":
                        raise ICtxErr("Condition returned non-int value")
                    if condval[1] == 0:
                        self.debug("0, breaking while loop")
                        break
                    self.debug("non-zero, running body")
                    ctx = ICtx(body[1], self.dbg, self.stack, self.vartable, self.inst + 1)
                    ctx.run()
                self.next()
            elif cl == ".":
                self.debug(f"Output called")
                val = self.stack.pop()
                if val[0] not in ("str", "int"):
                    raise ICtxErr(f"{val[0]} printing is not supported")
                print(val[1], end='')
                self.next()
            elif cl == "=":
                self.debug("Comparison called")
                self.stack.push(int(self.stack.pop()[1] == self.stack.pop()[1]))
                self.next()
            elif cl == "+":
                self.debug("Addition")
                top = self.stack.pop()
                btm = self.stack.pop()
                if (top[0], btm[0]) not in (("int", "int"), ("str", "str")):
                    raise ICtxErr(f"Can't add {top[0]} to {btm[0]}")
                self.stack.push(btm[1] + top[1])
                self.next()
            elif cl == "-":
                self.debug("Subtraction")
                top = self.stack.pop()
                btm = self.stack.pop()
                if top[0] != "int" or btm[0] != "int":
                    raise ICtxErr(f"Can't sub {top[0]} from {btm[0]}")
                self.stack.push(btm[1] - top[1])
                self.next()
            elif cl == "/":
                self.debug("Division")
                top = self.stack.pop()
                btm = self.stack.pop()
                if top[0] != "int" or btm[0] != "int":
                    raise ICtxErr(f"Can't divide {btm[0]} by {top[0]}")
                self.stack.push(btm[1] / top[1])
                self.next()
            elif cl == "*":
                self.debug("Multiply")
                top = self.stack.pop()
                btm = self.stack.pop()
                if top[0] != "int" or btm[0] != "int":
                    raise ICtxErr(f"Can't multiply {top[0]} by {btm[0]}")
                self.stack.push(top[1] * btm[1])
                self.next()
            elif cl == ",":
                self.debug("User input")
                self.stack.push(input())
                self.next()
            elif cl == "c":
                self.next()
                if self.cmd[0] != "call":
                    raise ICtxErr("Wrong conversion")
                self.debug(f"Conversion to {self.cmd[1]}")
                if self.cmd[1] == "i":
                    self.stack.push(int(self.stack.pop()[1]))
                elif self.cmd[1] == "s":
                    self.stack.push(str(self.stack.pop()[1]))
                else:
                    raise ICtxErr(f"Invalid conversion (to '{self.cmd[1]}')")
                self.next()
            elif cl == "!":
                self.debug("NOT operator")
                top = self.stack.pop()
                if top[0] != "int":
                    raise ICtxErr(f"Can't invert {top[0]}")
                self.stack.push(1 if top[1] == 0 else 0)
                self.next()
            else:
                self.debug("Unknown user call")
                raise ICtxErr(f"Unknown call {cl}")
        elif self.cmd[0] == "varassign":
            self.debug("VarAssign called")
            asgn = self.stack.pop()
            if asgn[0] not in ("str", "lambda", "int"):
                raise ICtxErr("Assigning invalid value to variable")
            self.vartable[self.cmd[1]] = asgn
            self.next()
        elif self.cmd[0] == "varread":
            self.debug("VarRead called")
            self.stack.push(self.vartable[self.cmd[1]])
            self.next()
        else:
            self.debug("Unknown token - ictx bug?")
            raise ICtxErr("unknown token - falshell bug? report on github.")


pstack = ManagedStack()
ptable = ManagedVar()


def main():
    print(f"Falshell v{VERSION}")
    print("Type ? to see help.")

    pth = os.path.expanduser("~")
    mode = "sh"
    debuggable = False

    while True:
        try:
            query = input(f"{clrGreen}{mode}{clrReset}:{clrBlue}{pth}{clrReset}] ")
        except (EOFError, KeyboardInterrupt) as ex:
            print("\nBye!")
            sys.exit(0)
        if query == "***DEBUG":
            debuggable = not debuggable
            print(f"Switched interpreter debug mode - now its {debuggable}")
            continue
        try:
            prg = Lexer(query).run()
        except LexerErr as ex:
            print(f"An error occured while parsing: {ex}")
            continue
        #print(prg)
        try:
            ctx = ICtx(prg, debuggable, pstack, ptable)
            ctx.run()
        except KeyboardInterrupt as ex:
            print("Execution stopped.")
        except ICtxErr as ex:
            print(f"An error occured while running: {ex}")
            continue


if len(sys.argv) < 2:
    main()
else:
    try:
        f = open(sys.argv[1]).read()
    except Exception as ex:
        print(f"Failed to read file: {ex}")
        sys.exit(1)
    try:
        prg = Lexer(f).run()
    except LexerErr as ex:
        print(f"An error occured while parsing: {ex}")
        sys.exit(1)
    try:
        ctx = ICtx(prg, False, pstack, ptable)
        ctx.run()
    except KeyboardInterrupt as ex:
        print("Execution stopped.")
    except ICtxErr as ex:
        print(f"An error occured while running: {ex}")
    sys.exit(1)
