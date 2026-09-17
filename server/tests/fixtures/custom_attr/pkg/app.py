from pkg import base


# Attribute-call instantiation of a cross-file custom class.
a = base.MyLlmCustom(name="a")

# Same class, but instantiation overrides model — merge should keep the
# override and pull instruction from super().__init__.
b = base.MyLlmCustom(name="b", model="gemini-2.0")
