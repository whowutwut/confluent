PATH=/opt/confluent/bin:$PATH
export PATH
MANPATH=/opt/confluent/share/man:$MANPATH
export MANPATH
# The aliases below are to signify that file globbing is unwelcome at the shell
# this avoids a problem if a user does a noderange like 'n[21-33] and there is a file
# in the directory like 'n3' that causes the parameter to change and target a totally
# different node
# Unfortunately in bourne shell, we cannot reliably ensure a prepended set-f
# and an appended set +f are both run.  alias seems to be the only mechanism
# that can intervene before glob expansion, but it lacks power.
# putting it into a function to append is all well and good, *except*  that
# if doing something like 'nodepower compute|grep' causes set -f to execute
# in current shell, and the function to be in a subshell and leaves globbing
# disabled in the parent shell.  Instead, store the current command in a
# variable and use that to check for misglobbed noderanges, which was the goal
alias nodeattrib='CURRENT_CMDLINE=$(HISTTIMEFORMAT= builtin history 1); export CURRENT_CMDLINE; nodeattrib'
alias nodebmcreset='CURRENT_CMDLINE=$(HISTTIMEFORMAT= builtin history 1); export CURRENT_CMDLINE; nodebmcreset'
alias nodeboot='CURRENT_CMDLINE=$(HISTTIMEFORMAT= builtin history 1); export CURRENT_CMDLINE; nodeboot'
alias nodeconfig='CURRENT_CMDLINE=$(HISTTIMEFORMAT= builtin history 1); export CURRENT_CMDLINE; nodeconfig'
alias nodeconsole='CURRENT_CMDLINE=$(HISTTIMEFORMAT= builtin history 1); export CURRENT_CMDLINE; nodeconsole'
alias nodedefine='CURRENT_CMDLINE=$(HISTTIMEFORMAT= builtin history 1); export CURRENT_CMDLINE; nodedefine'
alias nodeeventlog='CURRENT_CMDLINE=$(HISTTIMEFORMAT= builtin history 1); export CURRENT_CMDLINE; nodeeventlog'
alias nodefirmware='CURRENT_CMDLINE=$(HISTTIMEFORMAT= builtin history 1); export CURRENT_CMDLINE; nodefirmware'
alias nodegroupattrib='CURRENT_CMDLINE=$(HISTTIMEFORMAT= builtin history 1); export CURRENT_CMDLINE; nodegroupattrib'
alias nodegroupdefine='CURRENT_CMDLINE=$(HISTTIMEFORMAT= builtin history 1); export CURRENT_CMDLINE; nodegroupdefine'
alias nodegroupremove='CURRENT_CMDLINE=$(HISTTIMEFORMAT= builtin history 1); export CURRENT_CMDLINE; nodegroupremove'
alias nodehealth='CURRENT_CMDLINE=$(HISTTIMEFORMAT= builtin history 1); export CURRENT_CMDLINE; nodehealth'
alias nodeidentify='CURRENT_CMDLINE=$(HISTTIMEFORMAT= builtin history 1); export CURRENT_CMDLINE; nodeidentify'
alias nodeinventory='CURRENT_CMDLINE=$(HISTTIMEFORMAT= builtin history 1); export CURRENT_CMDLINE; nodeinventory'
alias nodelist='CURRENT_CMDLINE=$(HISTTIMEFORMAT= builtin history 1); export CURRENT_CMDLINE; nodelist'
alias nodemedia='CURRENT_CMDLINE=$(HISTTIMEFORMAT= builtin history 1); export CURRENT_CMDLINE; nodemedia'
alias nodepower='CURRENT_CMDLINE=$(HISTTIMEFORMAT= builtin history 1); export CURRENT_CMDLINE; nodepower'
alias noderemove='CURRENT_CMDLINE=$(HISTTIMEFORMAT= builtin history 1); export CURRENT_CMDLINE; noderemove'
alias nodereseat='CURRENT_CMDLINE=$(HISTTIMEFORMAT= builtin history 1); export CURRENT_CMDLINE; nodereseat'
alias noderun='CURRENT_CMDLINE=$(HISTTIMEFORMAT= builtin history 1); export CURRENT_CMDLINE; noderun'
alias nodesensors='CURRENT_CMDLINE=$(HISTTIMEFORMAT= builtin history 1); export CURRENT_CMDLINE; nodesensors'
alias nodesetboot='CURRENT_CMDLINE=$(HISTTIMEFORMAT= builtin history 1); export CURRENT_CMDLINE; nodesetboot'
alias nodestorage='CURRENT_CMDLINE=$(HISTTIMEFORMAT= builtin history 1); export CURRENT_CMDLINE; nodestorage'
alias nodeshell='CURRENT_CMDLINE=$(HISTTIMEFORMAT= builtin history 1); export CURRENT_CMDLINE; nodeshell'
alias nodelicense='CURRENT_CMDLINE=$(HISTTIMEFORMAT= builtin history 1); export CURRENT_CMDLINE; nodelicense'


_confluent_get_args()
{
    CMPARGS=($COMP_LINE)
    NUMARGS=${#CMPARGS[@]}
    if [ "${COMP_WORDS[-1]}" == '' ]; then
        NUMARGS=$((NUMARGS+1))
        CMPARGS+=("")
    fi
    GENNED=""
    for CAND in ${COMP_CANDIDATES[@]}; do
        candarray=(${CAND//,/ })
        matched=0
        for c in "${candarray[@]}"; do
            for arg in "${CMPARGS[@]}"; do
                if [ "$arg" = "$c" ]; then
                    matched=1
                    break
                fi
            done
        done
        if [ 0 = $matched ]; then
            for c in "${candarray[@]}"; do
                GENNED+=" $c"
            done
        fi
    done
}

function _confluent_generic_completion()
{
    _confluent_get_args
    if [ $NUMARGS -ge 3 ] && [ ! -z "$GENNED" ]; then
        COMPREPLY=($(compgen -W "$GENNED" -- ${COMP_WORDS[-1]}))
    fi
    if [ $NUMARGS -lt 3 ]; then
        _confluent_nr_completion
        return;
    fi
}
_confluent_nodeidentify_completion()
{
    COMP_CANDIDATES=("on,off -h")
    _confluent_generic_completion
}


_confluent_nodesetboot_completion()
{
    COMP_CANDIDATES=("default,cd,network,setup,hd -h -b -p")
    _confluent_generic_completion
}

_confluent_nodepower_completion()
{
   COMP_CANDIDATES=("boot,off,on,status -h -p")
   _confluent_generic_completion
}

_confluent_nodemedia_completion()
{
    COMP_CANDIDATES=("list,upload,attach,detachall -h")
    _confluent_get_args
    if [ $NUMARGS -gt 3 ] && [ ${CMPARGS[-2]} == 'upload' ]; then
        compopt -o default
        COMPREPLY=()
        return
    fi
    if [ $NUMARGS -ge 3 ] && [ ! -z "$GENNED" ]; then
        COMPREPLY=($(compgen -W "$GENNED" -- ${COMP_WORDS[-1]}))
        return;
    fi
    if [ $NUMARGS -lt 3 ]; then
        _confluent_nr_completion
        return;
    fi
}

_confluent_nodefirmware_completion()
{
    _confluent_get_args
    if [ $NUMARGS == 3 ]; then
        COMPREPLY=($(compgen -W "list update" -- ${COMP_WORDS[-1]}))
        return;
    fi
    if [ $NUMARGS -gt 3 ] && [ ${CMPARGS[2]} == 'update' ]; then
        compopt -o default
        COMPREPLY=()
        return
    fi
    if [ $NUMARGS -lt 3 ]; then
        _confluent_nr_completion
        return;
    fi
}

_confluent_nodeshell_completion()
{
    _confluent_get_args
    if [ $NUMARGS == 3 ]; then
        COMPREPLY=($(compgen -c -- ${COMP_WORDS[-1]}))
        return
    fi
    if [ $NUMARGS -gt 3 ]; then
        compopt -o default
        COMPREPLY=()
        return
    fi
    if [ $NUMARGS -lt 3 ]; then
        _confluent_nr_completion
        return;
    fi
}

_confluent_nodelicense_completion()
{
    _confluent_get_args
    if [ $NUMARGS == 3 ]; then
        COMPREPLY=($(compgen -W "install list" -- ${COMP_WORDS[-1]}))
        return;
    fi
    if [ $NUMARGS == 4 ] && [ ${CMPARGS[2]} == 'install' ]; then
        compopt -o default
        COMPREPLY=()
        return
    fi
    if [ $NUMARGS -lt 3 ]; then
         _confluent_nr_completion
         return
    fi
}

_confluent_nodesupport_completion()
{
    _confluent_get_args
    if [ $NUMARGS == 3 ]; then
        COMPREPLY=($(compgen -W "servicedata" -- ${COMP_WORDS[-1]}))
        return;
    fi
    if [ $NUMARGS == 4 ] && [ ${CMPARGS[2]} == 'servicedata' ]; then
        compopt -o  dirnames
        COMPREPLY=()
        return
    fi
    if [ $NUMARGS -lt 3 ]; then
         _confluent_nr_completion
         return
    fi
}

_confluent_nn_completion()
{
    _confluent_get_args
    if [ $NUMARGS -gt 2 ]; then
        return;
    fi
    INPUT=${COMP_WORDS[-1]}
    INPUT=${INPUT##*,-}
    INPUT=${INPUT##*,}
    INPUT=${INPUT##*@}
    PREFIX=""
    if [ "$INPUT" != "${COMP_WORDS[-1]}" ]; then
        PREFIX=${COMP_WORDS[-1]}
        PREFIX=$(echo $PREFIX | sed -e 's/,[^,@-]*$/,/' -e 's/,-[^,@]*$/,-/' -e 's/@[^,@]*/@/')
    fi

    COMPREPLY=($(compgen -W "$(nodelist | sed -e s/^/$PREFIX/)" -- "${COMP_WORDS[-1]}"))
}
_confluent_nr_completion()
{
    CMPARGS=($COMP_LINE)
    NUMARGS=${#CMPARGS[@]}
    if [ "${COMP_WORDS[-1]}" == '' ]; then
        NUMARGS=$((NUMARGS+1))
    fi
    _confluent_get_args
    if [ $NUMARGS -gt 2 ]; then
        return;
    fi
    INPUT=${COMP_WORDS[-1]}
    INPUT=${INPUT##*,-}
    INPUT=${INPUT##*,}
    INPUT=${INPUT##*@}
    PREFIX=""
    if [ "$INPUT" != "${COMP_WORDS[-1]}" ]; then
        PREFIX=${COMP_WORDS[-1]}
        PREFIX=$(echo $PREFIX | sed -e 's/,[^,@-]*$/,/' -e 's/,-[^,@]*$/,-/' -e 's/@[^,@]*/@/')
    fi

    #COMPREPLY=($(compgen -W "$(confetty show /nodegroups|sed -e 's/\///' -e s/^/$PREFIX/;nodelist | sed -e s/^/$PREFIX/)" -- "${COMP_WORDS[-1]}"))
    COMPREPLY=($(compgen -W "$(confetty show /nodegroups|sed -e 's/\///' -e s/^/$PREFIX/;nodelist | sed -e s/^/$PREFIX/)" -- "${COMP_WORDS[-1]}"))
}
_confluent_ng_completion()
{
    _confluent_get_args
    if [ $NUMARGS -gt 2 ]; then
        return;
    fi
    INPUT=${COMP_WORDS[-1]}
    INPUT=${INPUT##*,-}
    INPUT=${INPUT##*,}
    INPUT=${INPUT##*@}
    PREFIX=""
    if [ "$INPUT" != "${COMP_WORDS[-1]}" ]; then
        PREFIX=${COMP_WORDS[-1]}
        PREFIX=$(echo $PREFIX | sed -e 's/,[^,@-]*$/,/' -e 's/,-[^,@]*$/,-/' -e 's/@[^,@]*/@/')
    fi

    COMPREPLY=($(compgen -W "$(confetty show /nodegroups|sed -e 's/\///' -e s/^/$PREFIX/)" -- "${COMP_WORDS[-1]}"))
}
complete -F _confluent_nr_completion nodeattrib
complete -F _confluent_nr_completion nodebmcreset
complete -F _confluent_nodesetboot_completion nodeboot
complete -F _confluent_nr_completion nodeconfig
complete -F _confluent_nn_completion nodeconsole
complete -F _confluent_nr_completion nodeeventlog
complete -F _confluent_nodefirmware_completion nodefirmware
complete -F _confluent_ng_completion nodegroupattrib
complete -F _confluent_ng_completion nodegroupremove
complete -F _confluent_nr_completion nodehealth
complete -F _confluent_nodeidentify_completion nodeidentify
complete -F _confluent_nr_completion nodeinventory
complete -F _confluent_nr_completion nodelist
complete -F _confluent_nodemedia_completion nodemedia
complete -F _confluent_nodepower_completion nodepower
complete -F _confluent_nr_completion noderemove
complete -F _confluent_nr_completion nodereseat
complete -F _confluent_nodeshell_completion noderun
complete -F _confluent_nr_completion nodesensors
complete -F _confluent_nodesetboot_completion nodesetboot
complete -F _confluent_nodeshell_completion nodeshell
complete -F _confluent_nodesupport_completion nodesupport
complete -F _confluent_nodelicense_completion nodelicense

