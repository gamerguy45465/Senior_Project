#ifndef PYTHONSYNTAXHIGHLIGHTING_H
#define PYTHONSYNTAXHIGHLIGHTING_H


#include <QSyntaxHighlighter>
#include <QRegularExpression>

class PythonSyntaxHighlighting : public QSyntaxHighlighter
{
    Q_OBJECT
public:
    PythonSyntaxHighlighting(QTextDocument *parent = nullptr);

protected:
    void highlightBlock(const QString &text) override;


private:
    struct Rule {
      QRegularExpression pattern;
      QTextCharFormat format;
    };


    QVector<Rule> rules;
};

#endif // PYTHONSYNTAXHIGHLIGHTING_H
