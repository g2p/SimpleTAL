""" simpleTALUtils

		Copyright 2003 Colin Stewart (http://www.owlfish.com/)
		
		This code is made freely available for commercial and non-commercial
		use.  No warranties, expressed or implied, are made as to the
		fitness of this code for any purpose.
		
		If you make any bug fixes or feature enhancements please let me know!
		
		This module is holds utilities that make using SimpleTAL easier. 
		Initially this is just the HTMLStructureCleaner class, used to clean
		up HTML that can then be used as 'structure' content.
		
		Module Dependencies: None
"""

__version__ = "3.0"


import StringIO, os, sys, codecs, sgmllib, cgi, re

import simpleTAL

# This is used to check for already escaped attributes.
ESCAPED_TEXT_REGEX=re.compile (r"\&\S+?;")

class HTMLStructureCleaner (sgmllib.SGMLParser):
	""" A helper class that takes HTML content and parses it, so converting
			any stray '&', '<', or '>' symbols into their respective entity references.
	"""
	def clean (self, content, encoding=None):
		""" Takes the HTML content given, parses it, and converts stray markup.
				The content can be either:
					 - A unicode string, in which case the encoding parameter is not required
					 - An ordinary string, in which case the encoding will be used
					 - A file-like object, in which case the encoding will be used if present
				
				The method returns a unicode string which is suitable for addition to a
				simpleTALES.Context object.
		"""
		if (type (content) == type ("")):
			# Not unicode, convert
			converter = codecs.lookup (encoding)[1]
			file = StringIO.StringIO (converter (content)[0])
		elif (type (content) == type (u"")):
			file = StringIO.StringIO (content)
		else:
			# Treat it as a file type object - and convert it if we have an encoding
			if (encoding is not None):
				converterStream = codecs.lookup (encoding)[2]
				file = converterStream (content)
			else:
				file = content
		
		self.outputFile = StringIO.StringIO (u"")
		self.feed (file.read())
		self.close()
		return self.outputFile.getvalue()
		
	def unknown_starttag (self, tag, attributes):
		self.outputFile.write (tagAsText (tag, attributes))
		
	def unknown_endtag (self, tag):
		self.outputFile.write ('</' + tag + '>')
			
	def handle_data (self, data):
		self.outputFile.write (cgi.escape (data))
		
	def handle_charref (self, ref):
		self.outputFile.write (u'&#%s;' % ref)
		
	def handle_entityref (self, ref):
		self.outputFile.write (u'&%s;' % ref)
			

def tagAsText (tag,atts):
	result = "<" + tag 
	for name,value in atts:
		if (ESCAPED_TEXT_REGEX.search (value) is not None):
			# We already have some escaped characters in here, so assume it's all valid
			result += ' %s="%s"' % (name, value)
		else:
			result += ' %s="%s"' % (name, cgi.escape (value))
	result += ">"
	return result

class MacroExpansionInterpreter (simpleTAL.TemplateInterpreter):
	def __init__ (self):
		simpleTAL.TemplateInterpreter.__init__ (self)
		# Override the standard interpreter way of doing things.
		self.macroStateStack = []
		self.commandHandler [simpleTAL.TAL_DEFINE] = self.cmdNoOp
		self.commandHandler [simpleTAL.TAL_CONDITION] = self.cmdNoOp
		self.commandHandler [simpleTAL.TAL_REPEAT] = self.cmdNoOp
		self.commandHandler [simpleTAL.TAL_CONTENT] = self.cmdNoOp
		self.commandHandler [simpleTAL.TAL_ATTRIBUTES] = self.cmdNoOp
		self.commandHandler [simpleTAL.TAL_OMITTAG] = self.cmdNoOp
		self.commandHandler [simpleTAL.TAL_START_SCOPE] = self.cmdStartScope
		self.commandHandler [simpleTAL.TAL_OUTPUT] = self.cmdOutput
		self.commandHandler [simpleTAL.TAL_STARTTAG] = self.cmdOutputStartTag
		self.commandHandler [simpleTAL.TAL_ENDTAG_ENDSCOPE] = self.cmdEndTagEndScope
		self.commandHandler [simpleTAL.METAL_USE_MACRO] = self.cmdUseMacro
		self.commandHandler [simpleTAL.METAL_DEFINE_SLOT] = self.cmdDefineSlot
		self.commandHandler [simpleTAL.TAL_NOOP] = self.cmdNoOp
		
		self.inMacro = None
		self.macroArg = None
	# Original cmdOutput
	# Original cmdEndTagEndScope
		
	def popProgram (self):
		self.inMacro = self.macroStateStack.pop()
		simpleTAL.TemplateInterpreter.popProgram (self)
		
	def pushProgram (self):
		self.macroStateStack.append (self.inMacro)
		simpleTAL.TemplateInterpreter.pushProgram (self)
		
	def cmdOutputStartTag (self, command, args):
		newAtts = []
		for att in self.originalAttributes:
			if (self.macroArg is not None and att[0] == "metal:define-macro"):
				newAtts.append (("metal:use-macro",self.macroArg))
			elif (self.inMacro and att[0]=="metal:define-slot"):
				newAtts.append (("metal:fill-slot", att[1]))
			else:
				newAtts.append (att)
		self.macroArg = None
		self.currentAttributes = newAtts
		simpleTAL.TemplateInterpreter.cmdOutputStartTag (self, command, args)
		
	def cmdUseMacro (self, command, args):
		simpleTAL.TemplateInterpreter.cmdUseMacro (self, command, args)
		if (self.tagContent is not None):
			# We have a macro, add the args to the in-macro list
			self.inMacro = 1
			self.macroArg = args[0]
			
	def cmdEndTagEndScope (self, command, args):
		# Args: tagName, omitFlag
		if (self.tagContent is not None):
			contentType, resultVal = self.tagContent
			if (contentType):
				if (isinstance (resultVal, simpleTAL.Template)):
					# We have another template in the context, evaluate it!
					# Save our state!
					self.pushProgram()
					resultVal.expandInline (self.context, self.file, self)
					# Restore state
					self.popProgram()
					# End of the macro expansion (if any) so clear the parameters
					self.slotParameters = {}
					# End of the macro
					self.inMacro = 0
				else:
					if (type (resultVal) == type (u"")):
						self.file.write (resultVal)
					elif (type (resultVal) == type ("")):
						self.file.write (unicode (resultVal, 'ascii'))
					else:
						self.file.write (unicode (str (resultVal), 'ascii'))
			else:
				if (type (resultVal) == type (u"")):
					self.file.write (cgi.escape (resultVal))
				elif (type (resultVal) == type ("")):
					self.file.write (cgi.escape (unicode (resultVal, 'ascii')))
				else:
					self.file.write (cgi.escape (unicode (str (resultVal), 'ascii')))
					
		if (self.outputTag and not args[1]):
			self.file.write ('</' + args[0] + '>')
		
		if (self.movePCBack is not None):
			self.programCounter = self.movePCBack
			return
			
		if (self.localVarsDefined):
			self.context.popLocals()
			
		self.movePCForward,self.movePCBack,self.outputTag,self.originalAttributes,self.currentAttributes,self.repeatVariable,self.repeatIndex,self.repeatSequence,self.tagContent,self.localVarsDefined = self.scopeStack.pop()			
		self.programCounter += 1
			
def ExpandMacros (context, template, outputEncoding="ISO8859-1"):
	out = StringIO.StringIO()
	interp = MacroExpansionInterpreter()
	interp.initialise (context, out)
	template.expand (context, out, outputEncoding, interp)
	# StringIO returns unicode, so we need to turn it back into native string
	result = out.getvalue()
	reencoder = codecs.lookup (outputEncoding)[0]
	return reencoder (result)[0]
