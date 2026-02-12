#ifndef BACKEND_H
#define BACKEND_H

#include <QObject>
#include <QCoreApplication>
#include <QDir>
#include <QDebug>
#include <QProcess>
#include <QFileDialog>
#include <QFileInfo>
#include <QUrl>
#include <QStandardPaths>
#include <QProcessEnvironment>

class Backend : public QObject
{
    Q_OBJECT
    Q_PROPERTY(QString path READ path WRITE setPath NOTIFY pathChanged)
    Q_PROPERTY(QString data READ data WRITE setData NOTIFY dataChanged)
public:
    explicit Backend(QObject *parent = nullptr);


    void setEmittedState();



    QString path();
    void setPath(QString value);
    QString data();
    void setData(QString value);

    Q_INVOKABLE void runInTerminal(const QString &filePath, const QString &fileName);
signals:
    void pathChanged();
    void dataChanged();


//public Q_SLOTS:
public slots:
    void fileUrlChanged();
    bool getEmittedState();





private:
    QString m_path;
    bool emited_state;
};

#endif // BACKEND_H
