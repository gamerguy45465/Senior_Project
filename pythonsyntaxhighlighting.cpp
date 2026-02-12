#include "pythonsyntaxhighlighting.h"



PythonSyntaxHighlighting::PythonSyntaxHighlighting(QTextDocument *parent)
    : QSyntaxHighlighter(parent)
{
    QTextCharFormat keywordFormat;
    keywordFormat.setForeground(Qt::blue);
    keywordFormat.setFontWeight(QFont::Bold);


    QStringList keywords = {
        "and", "as", "assert", "break", "class", "continue", "def", "del", "elif", "else", "except", "False", "finally", "for", "from", "global", "if", "import", "in", "is", "lambda", "None", "nonlocal", "not", "or", "pass", "raise", "return", "True", "try", "while", "with", "yield"
    };

    QTextCharFormat builtinFormat;
    builtinFormat.setForeground(Qt::red);



    QStringList builtins = {
        "print", "len", "range", "str", "int", "float", "list", "dict", "set", "tuple", "open", "sum", "min", "max", "abs", "enumerate", "zip", "map", "filter", "sorted"
    };




    for(const QString &word : keywords) {
        rules.append({
                QRegularExpression("\\b" + word + "\\b"),
                keywordFormat
        });

    }

    for(const QString &word : builtins) {
        rules.append({
                 QRegularExpression("\\b" + word + "\\b"),
                 builtinFormat});
    }

    QTextCharFormat stringFormat;
    stringFormat.setForeground(Qt::darkGreen);
    rules.append({QRegularExpression("\".*\""), stringFormat});
    rules.append({QRegularExpression("\'.*\'"), stringFormat});


    QTextCharFormat commentFormat;
    commentFormat.setForeground(Qt::gray);
    rules.append({QRegularExpression("#[^\n]*"), commentFormat});


}

void PythonSyntaxHighlighting::highlightBlock(const QString &text)
{
    for (const Rule &rule : rules) {
        auto it = rule.pattern.globalMatch(text);
        while(it.hasNext()) {
            auto match = it.next();
            setFormat(match.capturedStart(), match.capturedLength(), rule.format);
        }
    }

}
